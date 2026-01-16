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


def test_version_endpoint(backend_host):
    """Test that /api/version endpoint returns 200 OK."""
    r = requests.get(f"{backend_host}/api/version", verify=False)
    assert r.status_code == 200, f"Expected 200 OK, got {r.status_code}"
    logger.info(f"Version endpoint returned 200 OK")

    # Verify Content-Type is JSON
    content_type = r.headers.get("Content-Type", "")
    assert "application/json" in content_type, f"Expected JSON content type, got {content_type}"

    # Verify response can be parsed as JSON
    response_json = r.json()
    assert "version" in response_json, f"Expected 'version' field in response, got: {response_json}"

    version = response_json["version"]
    assert isinstance(version, str), f"Expected version to be string, got {type(version)}"
    assert len(version) > 0, "Version string should not be empty"

    logger.info(f"Version endpoint returned version: {version}")


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
    # Switch configuration
    "switchRotation": 0,
    "switchSide": "FRONT",
    # Diode configuration
    "diodeRotation": 90,
    "diodeSide": "BACK",
    "diodePositionX": 5.08,
    "diodePositionY": 4.0,
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
        "switchRotation": 0,
        "switchSide": "FRONT",
        "diodeRotation": 90,
        "diodeSide": "BACK",
        "diodePositionX": 5.08,
        "diodePositionY": 4.0,
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


@pytest.mark.parametrize(
    "switch_rotation,switch_side,diode_rotation,diode_side,diode_x,diode_y",
    [
        # Test different rotations with default sides
        (0, "FRONT", 0, "BACK", 5.0, -4.5),
        (90, "FRONT", 90, "BACK", 5.0, -4.5),
        (180, "FRONT", 180, "BACK", 5.0, -4.5),
        (270, "FRONT", 270, "BACK", 5.0, -4.5),
        # Test different side combinations
        (0, "FRONT", 0, "FRONT", 5.0, -4.5),
        (0, "BACK", 0, "BACK", 5.0, -4.5),
        (0, "BACK", 0, "FRONT", 5.0, -4.5),
        # Test different diode positions
        (0, "FRONT", 0, "BACK", 0.0, 0.0),
        (0, "FRONT", 0, "BACK", -5.0, 4.5),
        (0, "FRONT", 0, "BACK", 10.0, -10.0),
    ],
)
def test_switch_diode_configurations(
    request,
    tmpdir,
    pcb_endpoint,
    switch_rotation,
    switch_side,
    diode_rotation,
    diode_side,
    diode_x,
    diode_y,
):
    """Test different switch and diode configuration combinations."""
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    settings = {
        "controllerCircuit": "None",
        "routing": "Full",
        "switchFootprint": FOOTPRINTS_OPTIONS_MAP["MX"],
        "diodeFootprint": "Diode_SMD:D_SOD-123F",
        "switchRotation": switch_rotation,
        "switchSide": switch_side,
        "diodeRotation": diode_rotation,
        "diodeSide": diode_side,
        "diodePositionX": diode_x,
        "diodePositionY": diode_y,
    }
    layout_test_steps(tmpdir, pcb_endpoint, layout_file, settings)


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
    assert (
        "invalid layout metadata" in str(task_result).lower()
    ), f"Expected validation error, got: {task_result}"


# Error Details Tests


def test_failure_includes_error_details(tmpdir, pcb_endpoint):
    """Test that validation failures include detailed error information."""
    layout_file = f"{tmpdir}/invalid_metadata.json"
    # Create layout with missing required metadata
    invalid_layout = {"keys": []}  # Missing 'meta' field
    with open(layout_file, "w") as f:
        json.dump(invalid_layout, f)

    with open(layout_file) as f:
        layout_json = json.loads(f.read())
    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task should complete (with failure)"

    # Verify error field exists
    assert task_result.get("error") is not None, "Expected error field in task result"
    error_msg = str(task_result.get("error"))

    # Verify error contains meaningful details (not just a generic message)
    assert (
        len(error_msg) > 20
    ), f"Error message too short, expected details: {error_msg}"
    assert (
        "invalid" in error_msg.lower() or "metadata" in error_msg.lower()
    ), f"Expected specific error details, got: {error_msg}"

    logger.info(f"Error details received: {error_msg[:200]}")


def test_invalid_footprint_format_error_details(tmpdir, pcb_endpoint):
    """Test that invalid footprint format errors include detailed information."""
    layout_file = f"{tmpdir}/valid_layout_invalid_footprint.json"
    # Use a simple valid layout structure
    layout_data = {"meta": {"name": "test"}, "keys": [{"x": 0, "y": 0}]}
    with open(layout_file, "w") as f:
        json.dump(layout_data, f)

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    # Provide invalid footprint format (missing colon separator)
    invalid_settings = dict(DEFAULT_SETTINGS)
    invalid_settings["switchFootprint"] = "InvalidFormatNoColon"  # Should be "lib:footprint"

    request_data = {"layout": layout_json, "settings": invalid_settings}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task should complete (with failure)"

    # Verify error details are present
    assert task_result.get("error") is not None, "Expected error field in task result"
    error_msg = str(task_result.get("error"))

    # Verify error is descriptive
    assert len(error_msg) > 30, f"Error message too short: {error_msg}"
    assert (
        "footprint" in error_msg.lower()
    ), f"Expected footprint-related error: {error_msg}"

    # Verify it mentions the format requirement
    assert (
        "format" in error_msg.lower() or ":" in error_msg or "lib" in error_msg.lower()
    ), f"Expected error to mention format requirement: {error_msg}"

    logger.info(f"Footprint format error details: {error_msg[:200]}")


def test_missing_switch_rotation_field(tmpdir, pcb_endpoint):
    """Test that missing switchRotation field returns a detailed error."""
    layout_file = f"{tmpdir}/valid_layout_missing_field.json"
    layout_data = {"meta": {"name": "test"}, "keys": [{"x": 0, "y": 0}]}
    with open(layout_file, "w") as f:
        json.dump(layout_data, f)

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    # Settings missing switchRotation field
    incomplete_settings = dict(DEFAULT_SETTINGS)
    del incomplete_settings["switchRotation"]

    request_data = {"layout": layout_json, "settings": incomplete_settings}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task should complete (with failure)"

    # Verify error details are present
    assert task_result.get("error") is not None, "Expected error field in task result"
    error_msg = str(task_result.get("error"))

    # Verify error mentions the missing field
    assert (
        "switchRotation" in error_msg or "switch" in error_msg.lower()
    ), f"Expected error about missing switchRotation: {error_msg}"

    logger.info(f"Missing field error: {error_msg[:200]}")


def test_invalid_switch_side_value(tmpdir, pcb_endpoint):
    """Test that invalid switchSide value returns a detailed error."""
    layout_file = f"{tmpdir}/valid_layout_invalid_side.json"
    layout_data = {"meta": {"name": "test"}, "keys": [{"x": 0, "y": 0}]}
    with open(layout_file, "w") as f:
        json.dump(layout_data, f)

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    # Settings with invalid switchSide value
    invalid_settings = dict(DEFAULT_SETTINGS)
    invalid_settings["switchSide"] = "MIDDLE"  # Invalid value, should be FRONT or BACK

    request_data = {"layout": layout_json, "settings": invalid_settings}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task should complete (with failure)"

    # Verify error details are present
    assert task_result.get("error") is not None, "Expected error field in task result"
    error_msg = str(task_result.get("error"))

    # Verify error mentions the invalid side value
    assert (
        "switchSide" in error_msg or "FRONT" in error_msg or "BACK" in error_msg
    ), f"Expected error about invalid switchSide: {error_msg}"

    logger.info(f"Invalid side value error: {error_msg[:200]}")


def test_kbplacer_failure_includes_build_log(request, pcb_endpoint):
    """Test that kbplacer failures include build log content for debugging.

    This test creates a layout that will pass validation but cause kbplacer to fail,
    ensuring that the build log is included in the error response.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    # Modify layout to cause kbplacer failure (invalid key data)
    # Add a key with invalid properties that will trigger kbplacer error
    if "keys" in layout_json:
        # Add a malformed key entry
        layout_json["keys"].append(
            {
                "x": "invalid_x_coordinate",  # Should be number, not string
                "y": "invalid_y_coordinate",
                "w": -5,  # Negative width
                "h": -5,  # Negative height
            }
        )

    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_done, task_result = results[0][1], results[0][2]
    assert task_done == True, "Task should complete (with failure)"

    # Verify error exists
    assert task_result.get("error") is not None, "Expected error in task result"
    error_msg = str(task_result.get("error"))

    # Verify error contains substantial details (build log content)
    assert (
        len(error_msg) > 100
    ), f"Error message should include build log details, got {len(error_msg)} chars: {error_msg[:100]}"

    # Check for indicators that build log was included
    # These are common patterns in build logs or error details
    build_log_indicators = [
        "kbplacer",
        "failed",
        "error",
        "traceback",
        "build log",
        "INFO",
        "ERROR",
        "WARNING",
    ]

    has_indicator = any(
        indicator.lower() in error_msg.lower() for indicator in build_log_indicators
    )
    assert (
        has_indicator
    ), f"Expected error to include build log details with indicators like {build_log_indicators}, got: {error_msg[:200]}"

    logger.info(f"Build log error length: {len(error_msg)} chars")
    logger.info(f"Build log error preview: {error_msg[:300]}")


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
            "switchRotation": 0,
            "switchSide": "FRONT",
            "diodeRotation": 90,
            "diodeSide": "BACK",
            "diodePositionX": 5.08,
            "diodePositionY": 4.0,
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


# Task Cancellation Tests


def test_cancel_nonexistent_task(pcb_endpoint):
    """Test DELETE on a non-existent task should return 404."""
    task_id = "non-existent-task-id"
    r = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)
    assert r.status_code == 404
    response_json = r.json()
    assert "error" in response_json
    assert "not found" in response_json["error"].lower()


def test_cancel_pending_task(request, pcb_endpoint):
    """Test canceling a pending task should return 200 OK."""
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    # Submit task
    r = requests.post(pcb_endpoint, json=request_data, verify=False)
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    logger.info(f"Created task for cancellation test: {task_id}")

    # Cancel immediately while task is likely still pending
    r = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)

    # Should be 200 OK or 409 Conflict (if task started very quickly)
    assert r.status_code in [200, 409], f"Unexpected status code: {r.status_code}"

    if r.status_code == 200:
        response_json = r.json()
        assert response_json["task_id"] == task_id
        assert response_json["status"] == "cancelled"
        assert "message" in response_json
        logger.info(f"Successfully cancelled task: {task_id}")
    else:
        logger.info(f"Task {task_id} already started, could not cancel (409 Conflict)")


def test_cancel_completed_task(request, pcb_endpoint):
    """Test canceling a completed task should return 410 Gone."""
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    # Submit task and wait for completion
    results = [None]
    run_pcb_task(pcb_endpoint, request_data, results, 0)

    assert results[0]
    task_id, task_done = results[0][0], results[0][1]
    assert task_done == True, "Task should complete successfully"
    logger.info(f"Task completed: {task_id}")

    # Try to cancel completed task
    r = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)
    assert r.status_code == 410, f"Expected 410 Gone, got {r.status_code}"
    response_json = r.json()
    assert "error" in response_json
    assert (
        "completed" in response_json["error"].lower()
        or "gone" in response_json["error"].lower()
    )


def test_cancel_active_task(request, pcb_endpoint):
    """Test that canceling an active (running) task returns 409 Conflict.

    This test attempts to cancel a task while it's actively running.
    Due to timing, this may not always catch the task in ACTIVE state,
    but will verify the 409 response when it does.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    # Submit task
    r = requests.post(pcb_endpoint, json=request_data, verify=False)
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    logger.info(f"Created task for active cancellation test: {task_id}")

    # Poll until task becomes active, then try to cancel
    max_attempts = 20
    found_active = False

    for attempt in range(max_attempts):
        time.sleep(0.5)  # Check every 500ms

        # Check task status
        r_status = requests.get(f"{pcb_endpoint}/{task_id}", verify=False)
        if r_status.status_code == 200:
            status = r_status.json()["task_status"]
            logger.info(f"Attempt {attempt + 1}: Task status = {status}")

            if status == "PROGRESS":
                # Task is active/running, try to cancel
                found_active = True
                r_delete = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)

                # Should return 409 Conflict for active tasks
                assert (
                    r_delete.status_code == 409
                ), f"Expected 409 Conflict for active task, got {r_delete.status_code}"
                response_json = r_delete.json()
                assert "error" in response_json
                assert (
                    "running" in response_json["error"].lower()
                    or "active" in response_json["error"].lower()
                )
                logger.info(
                    f"Successfully verified 409 Conflict for active task: {task_id}"
                )
                break

            elif status == "SUCCESS" or status == "FAILURE":
                # Task completed before we could cancel it
                logger.warning(f"Task completed before cancellation attempt: {status}")
                break

    # If we never caught it in ACTIVE state, log a warning but don't fail
    # (this is a timing-dependent test)
    if not found_active:
        logger.warning(
            f"Could not catch task {task_id} in ACTIVE state within {max_attempts} attempts"
        )
        pytest.skip("Could not catch task in ACTIVE state (timing-dependent test)")


def test_double_cancellation(request, pcb_endpoint):
    """Test that canceling an already-cancelled task returns 404."""
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/2x2_internal.json"

    with open(layout_file) as f:
        layout_json = json.loads(f.read())

    request_data = {"layout": layout_json, "settings": DEFAULT_SETTINGS}

    # Submit task
    r = requests.post(pcb_endpoint, json=request_data, verify=False)
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    logger.info(f"Created task for double cancellation test: {task_id}")

    # First cancellation - should succeed or fail with 409 if already active
    r_first = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)
    assert r_first.status_code in [
        200,
        409,
    ], f"First cancellation failed with unexpected code: {r_first.status_code}"

    if r_first.status_code == 200:
        logger.info(f"First cancellation succeeded: {task_id}")

        # Second cancellation - should return 404 since task was removed
        time.sleep(0.5)  # Small delay to ensure cleanup
        r_second = requests.delete(f"{pcb_endpoint}/{task_id}", verify=False)
        assert (
            r_second.status_code == 404
        ), f"Expected 404 for second cancellation, got {r_second.status_code}"
        response_json = r_second.json()
        assert "error" in response_json
        assert "not found" in response_json["error"].lower()
        logger.info(f"Successfully verified 404 for double cancellation: {task_id}")
    else:
        logger.info(
            f"Task {task_id} was already active (409), skipping double cancellation test"
        )

