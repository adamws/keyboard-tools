import os
import pytest
import re
import time

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec


@pytest.mark.parametrize(
        "layout", ["2x2", "arisu"]
)
def test_correct_layout(layout, selenium, request, download_dir):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)
    layout_file = f"{test_dir}/{layout}.json"

    input_file = selenium.find_element("xpath", "//input[@id='file']")
    selenium.execute_script(
        'arguments[0].style = ""; arguments[0].style.display = "block"; arguments[0].style.visibility = "visible";',
        input_file,
    )
    input_file.send_keys(layout_file)
    download_btn = WebDriverWait(selenium, 60).until(
        ec.element_to_be_clickable((By.XPATH, "//button[@id='download-btn']")), 60
    )
    download_btn.click()

    download_link = selenium.find_element("xpath", "//a[@id='download']")
    link = download_link.get_attribute("href")
    job_id = re.search("http://.*/api/pcb/(.*)/result", link).group(1)

    # note that file is downloaded in selenium container to path /home/seluser/Downloads,
    # which should be mounted here:
    download_file = f"{download_dir}/{job_id}.zip"

    timeout = 60
    mustend = time.time() + timeout
    while time.time() < mustend:
        if os.path.exists(download_file):
            return True
        time.sleep(1)

    assert os.path.isfile(download_file)
