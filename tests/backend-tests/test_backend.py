import json
import logging
import os
import pytest
import random
import requests
import time

from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_pcb_task(backend, request_data, results, index):
    timeout_when_started = 180
    task_id = ""
    task_done = False
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
                if r.status_code == 200:
                    status = r.json()["task_status"]
                    if status == "SUCCESS":
                        task_done = True
                        break
                    elif status == "PENDING":
                        # prefetched, waiting for execution, can reset timeout, if we are to long in
                        # PENDING then whole thread will timeout
                        start_time = time.time()
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
            break
    results[index] = (task_id, task_done)


def test_multiple_concurrent_requests(pcb_endpoint, request):
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
            "keyDistance": "19.05 19.05",
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


def test_get_task_status_before_request(pcb_endpoint, request):
    task_id = "made-up-task-id"
    r = requests.get(f"{pcb_endpoint}/{task_id}", verify=False)
    assert r.status_code == 404


def test_get_task_result_before_request(pcb_endpoint, request):
    task_id = "made-up-task-id"
    r = requests.get(f"{pcb_endpoint}/{task_id}/result", verify=False)
    assert r.status_code == 404


def test_get_task_render_before_request(pcb_endpoint, request):
    task_id = "made-up-task-id"
    for side in ["front", "back"]:
        r = requests.get(f"{pcb_endpoint}/{task_id}/render/{side}", verify=False)
        assert r.status_code == 404
