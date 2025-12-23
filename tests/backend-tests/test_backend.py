import json
import logging
import os
import pytest
import random
import re
import requests
import time
import zipfile

from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FOOTPRINTS_OPTIONS_MAP = {
    "MX": "Switch_Keyboard_Cherry_MX:SW_Cherry_MX_PCB_{:.2f}u",
    "Alps": "Switch_Keyboard_Alps_Matias:SW_Alps_Matias_{:.2f}u",
    "MX/Alps Hybrid": "Switch_Keyboard_Hybrid:SW_Hybrid_Cherry_MX_Alps_{:.2f}u",
    "Hotswap Kailh MX": "Switch_Keyboard_Hotswap_Kailh:SW_Hotswap_Kailh_MX_{:.2f}u",
}

DEFAULT_SETTINGS = {
    "controllerCircuit": "None",
    "routing": "Full",
    "switchFootprint": FOOTPRINTS_OPTIONS_MAP["MX"],
    "diodeFootprint": "Diode_SMD:D_SOD-123F",
}


def assert_zip_content(zipfile, expected_name):
    files_in_zip = zipfile.namelist()
    assert "logs/build.log" in files_in_zip
    expected_in_keyboard_dir = [
        f"{expected_name}.kicad_pro",
        f"{expected_name}.kicad_pcb",
        f"{expected_name}.kicad_sch",
    ]
    for name in expected_in_keyboard_dir:
        assert f"{expected_name}/{name}" in files_in_zip


def extract_distances(log_message):
    pattern = r"distance:\s(\d+)/(\d+)"
    match = re.search(pattern, log_message)
    if match:
        distance1 = int(match.group(1))
        distance2 = int(match.group(2))
        return distance1, distance2
    else:
        return None


def get_artifacts(tmpdir, backend, task_id):
    for name in ["front", "back", "schematic"]:
        r = requests.get(f"{backend}/{task_id}/render/{name}", verify=False)
        with open(tmpdir / f"{name}.svg", "wb") as f:
            f.write(r.content)
        with requests.get(
            f"{backend}/{task_id}/result", stream=True, verify=False
        ) as r:
            r.raise_for_status()
            with open(tmpdir / "result.zip", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)


def run_pcb_task(backend, request_data, results, index):
    timeout_when_started = 180
    task_id = ""
    task_done = False
    task_result = ""
    cancelled = False
    while not task_done and not cancelled:
        r = requests.post(backend, json=request_data, verify=False)
        if r.status_code == 202:
            # task accepted, poll for result
            task_id = r.json()["task_id"]
            logger.info(f"Task {index} accepted, task id: {task_id}")
            start_time = time.time()
            while True:
                r = requests.get(f"{backend}/{task_id}", verify=False)
                logger.info(r.content)
                if r.status_code == 200:
                    status = r.json()["task_status"]
                    if status == "SUCCESS":
                        task_done = True
                        break
                    elif status == "PENDING":
                        # prefetched, waiting for execution, can reset timeout, if we are to long in
                        # PENDING then whole thread will timeout
                        start_time = time.time()
                    elif status == "FAILURE":
                        task_done = True
                        task_result = r.json()["task_result"]
                        break
                elif r.status_code == 404:
                    # if task was accepted but status query returns 404 then most likely
                    # it is not yet acknowledged by celery, it should be found in 'unacked'
                    # redis queue but sometimes we are to early even for that.
                    pass
                else:
                    # something went wrong, unexpected error
                    logger.error(
                        f"Unexpected error, task id: {task_id}, return code: {r.status_code}"
                    )
                    cancelled = True
                    break

                elapsed_time = time.time() - start_time
                if elapsed_time >= timeout_when_started:
                    logger.info(f"Task {task_id} timeout")
                    cancelled = True
                    break

                time.sleep(5)
        elif r.status_code == 503:
            # to many tasks enqueued, try again later
            logger.info(f"Task {index} not accepted, waiting for worker")
            time.sleep(10)
        else:
            # something went wrong, unexpected error
            logger.error(r.content)
            break
    results[index] = (task_id, task_done, task_result)


def layout_test_steps(
    tmpdir, pcb_endpoint, layout_file, settings, expected_name="keyboard"
):
    with open(layout_file) as f:
        layout_json = json.loads(f.read())
    request_data = {"layout": layout_json, "settings": settings}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_id, task_done = results[0][0], results[0][1]
    assert task_done == True, "Task failed"
    get_artifacts(tmpdir, pcb_endpoint, task_id)

    with zipfile.ZipFile(tmpdir / "result.zip", "r") as result:
        assert_zip_content(result, expected_name)


@pytest.mark.parametrize("layout", ["2x2_internal", "arisu_internal"])
# `Hotswap Kailh MX` not included, testing all combinations would
# trigger circle ci limits, better approach needed:
@pytest.mark.parametrize("switch_footprint", ["MX", "Alps", "MX/Alps Hybrid"])
@pytest.mark.parametrize("routing", ["Disabled", "Full"])
def test_correct_layout(
    request,
    tmpdir,
    layout,
    switch_footprint,
    routing,
    pcb_endpoint,
):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/{layout}.json"

    settings = {
        "controllerCircuit": "None",
        "routing": routing,
        "switchFootprint": FOOTPRINTS_OPTIONS_MAP[switch_footprint],
        "diodeFootprint": "Diode_SMD:D_SOD-123F",
    }
    layout_test_steps(tmpdir, pcb_endpoint, layout_file, settings)


def test_layout_with_various_key_sizes(request, tmpdir, pcb_endpoint):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/sizes_internal.json"

    layout_test_steps(tmpdir, pcb_endpoint, layout_file, DEFAULT_SETTINGS)


def test_layout_with_non_default_key_distance(request, tmpdir, pcb_endpoint):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal_custom_sizing.json"

    layout_test_steps(tmpdir, pcb_endpoint, layout_file, DEFAULT_SETTINGS)


def test_layout_with_name(request, tmpdir, pcb_endpoint):
    """Test if layout name sanitization works.
    Some characters are illegal and should be removed, for example to
    prevent creating directories outside allowed work directory.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file, "r") as f:
        layout_json = json.loads(f.read())
        layout_json["meta"]["name"] = "../60% /&lay//out"
        with open(tmpdir / "2x2_internal.json", "w") as f2:
            json.dump(layout_json, f2)

    layout_test_steps(
        tmpdir,
        pcb_endpoint,
        f"{tmpdir}/2x2_internal.json",
        DEFAULT_SETTINGS,
        "60% &layout",  # Leading ".." is stripped for security (path traversal prevention)
    )


def test_incorrect_layout(tmpdir, pcb_endpoint):
    layout_file = f"{tmpdir}/incorrect_layout.json"
    with open(layout_file, "w") as f:
        f.write("{}")

    with open(layout_file) as f:
        layout_json = json.loads(f.read())
    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task did not end"
    # With asynq, validation errors return structured error messages (not Python tracebacks)
    assert task_result.get("error") is not None, "Expected error in task result"
    assert "invalid layout metadata" in str(task_result).lower(), f"Expected validation error, got: {task_result}"


def test_multiple_concurrent_requests(request, pcb_endpoint):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_files = ["arisu_internal.json", "2x2_internal.json"]

    layouts = []
    for layout in layout_files:
        with open(f"{test_dir}/{layout}") as f:
            layouts.append(json.loads(f.read()))

    footprint_options = [
        "Switch_Keyboard_Cherry_MX:SW_Cherry_MX_PCB_{:.2f}u",
        "Switch_Keyboard_Alps_Matias:SW_Alps_Matias_{:.2f}u",
        "Switch_Keyboard_Hybrid:SW_Hybrid_Cherry_MX_Alps_{:.2f}u",
        "Switch_Keyboard_Hotswap_Kailh:SW_Hotswap_Kailh_MX_{:.2f}u",
    ]
    routing_options = ["Disabled", "Full"]

    # simulate many requests at the same time, server let's 2 waiting tasks in queue (not running or prefetched)
    # so '2 * cpu_count + 5' should cover all scenarios (when using prefetch_multipler = 1):
    # - task starts immediately
    # - task is added to queue but waits for worker
    # - task is not added to queue, need to re-try
    # Doing +5 instead of +3 to have some margin due to race conditions,
    # we do not care is some tasks slip through rate limiting mechanism in very unelikely scenario of many requests
    # at same time
    cpu_count = os.cpu_count()
    logger.info(f"Running on test host with {cpu_count} cpus")
    number_of_tasks = 2 * cpu_count + 5
    threads = []
    results = [None] * number_of_tasks
    for i in range(number_of_tasks):
        settings = {
            "controllerCircuit": "None",
            "routing": random.choice(routing_options),
            "switchFootprint": random.choice(footprint_options),
            "diodeFootprint": "Diode_SMD:D_SOD-123F",
        }
        request_data = {"layout": random.choice(layouts), "settings": settings}
        t = Thread(target=run_pcb_task, args=[pcb_endpoint, request_data, results, i])
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join(60.0 * 5)

    for result in results:
        assert result[1] == True, f"Task {result[0]} failed"


def test_get_task_status_before_request(pcb_endpoint):
    task_id = "made-up-task-id"
    r = requests.get(f"{pcb_endpoint}/{task_id}", verify=False)
    assert r.status_code == 404


def test_get_task_result_before_request(pcb_endpoint):
    task_id = "made-up-task-id"
    r = requests.get(f"{pcb_endpoint}/{task_id}/result", verify=False)
    assert r.status_code == 404


def test_get_task_render_before_request(pcb_endpoint):
    task_id = "made-up-task-id"
    for side in ["front", "back"]:
        r = requests.get(f"{pcb_endpoint}/{task_id}/render/{side}", verify=False)
        assert r.status_code == 404
