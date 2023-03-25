import json
import logging
import os
import pytest
import re
import time
import zipfile

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def assert_kicad_log(log_file, layout_file):
    layout = None
    with open(layout_file) as f:
        layout = json.loads(f.read())

    # very simplistic parse of keyboard layout file just to get number of keys:
    number_of_keys = 0
    for row in layout:
        for el in row:
            # strings represents keys
            if type(el) == str:
                number_of_keys += 1
            # other objects represents key properties, don't care about them yet

    # perform basic checks if log looks ok, not ideal because will fail with basic log file format change
    # but easiest to validate if generated pcb is at least likely to be correct.
    log_lines = log_file.readlines()

    # check if expected number of keys are placed in log in expected order:
    next_key = 1
    for line in log_lines:
        if f"Setting SW{next_key} footprint position:" in line.decode("utf-8"):
            next_key += 1

    assert next_key == number_of_keys + 1


@pytest.mark.parametrize("layout", ["2x2", "arisu"])
@pytest.mark.parametrize("footprint", ["MX", "Alps", "MX/Alps Hybrid"])
@pytest.mark.parametrize("routing", ["Disabled", "Full"])
@pytest.mark.parametrize("controller_circuit", ["None", "ATmega32U4"])
def test_correct_layout_no_matrix_predefined(
    layout,
    footprint,
    routing,
    controller_circuit,
    selenium,
    request,
    download_dir,
):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/{layout}.json"

    for option in [footprint, routing, controller_circuit]:
        span = selenium.find_element("xpath", f"//span[contains(.,'{option}')]")
        span.click()

    input_file = selenium.find_element("xpath", "//input[@id='file']")
    input_file.send_keys(layout_file)
    logger.info("Layout uploaded, started PCB generation")

    button = WebDriverWait(selenium, 60).until(
        ec.any_of(
            ec.element_to_be_clickable((By.XPATH, "//button[@id='download-btn']")),
            ec.element_to_be_clickable(
                (By.XPATH, "//*[@class='el-message-box__btns']/button")
            ),
        )
    )
    assert "download-btn" in button.get_attribute("id")

    logger.info("PCB done, downloading")
    button.click()

    download_link = selenium.find_element("xpath", "//a[@id='download']")
    link = download_link.get_attribute("href")

    job_id = re.search(f"{selenium.current_url}api/pcb/(.*)/result", link).group(1)

    download_file = f"{download_dir}/{job_id}.zip"

    timeout = 60
    mustend = time.time() + timeout
    while time.time() < mustend:
        if os.path.exists(download_file):
            break
        time.sleep(1)
    logger.info("Download done")

    assert os.path.isfile(download_file)

    with zipfile.ZipFile(download_file, "r") as result:
        files_in_zip = result.namelist()
        assert "logs/kbplacer.log" in files_in_zip
        expected_in_keyboard_dir = [
            "sym-lib-table",
            "keyboard.net",
            "keyboard.kicad_pro",
            "keyboard.kicad_pcb",
        ]
        for name in expected_in_keyboard_dir:
            assert f"keyboard/{name}" in files_in_zip

        with result.open("logs/kbplacer.log") as log_file:
            assert_kicad_log(log_file, layout_file)


def test_incorrect_layout_expect_error_window(tmpdir, selenium):
    layout_file = f"{tmpdir}/incorrect_layout.json"
    with open(layout_file, "w") as f:
        f.write("someunexpectedstuff")
    input_file = selenium.find_element("xpath", "//input[@id='file']")
    input_file.send_keys(layout_file)
    logger.info("Layout uploaded, started PCB generation")

    # expect message box with button
    button = WebDriverWait(selenium, 5).until(
        ec.element_to_be_clickable(
            (By.XPATH, "//*[@class='el-message-box__btns']/button")
        )
    )
    assert button
    assert not ("download-btn" in button.get_attribute("id"))
