import base64
import os
import pytest
import subprocess

from PIL import Image
from selenium import webdriver


def is_circleci():
    return "CI" in os.environ


@pytest.fixture(scope="session")
def selenium_data_path():
    return "/home/seluser/data"


@pytest.fixture(scope="session")
def website():
    return "http://app:8080"


def to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@pytest.mark.hookwrapper
def pytest_runtest_makereport(item, call):
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    extra = getattr(report, "extra", [])

    if report.when == "teardown":
        tmpdir = item.funcargs["tmpdir"]
        encoded = to_base64(f"{tmpdir}/screenshot.png")
        html = f"<div class='image'><img src='data:image/png;base64,{encoded}'></div>"
        extra.append(pytest_html.extras.html(html))
        report.extra = extra


@pytest.fixture(scope="session")
def driver(selenium_data_path):
    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.download.dir", f"{selenium_data_path}/downloads")
    _driver = webdriver.Remote(
        command_executor="http://localhost:4444/wd/hub", options=options
    )
    yield _driver
    _driver.quit()


def full_screenshot(driver, tmpdir):
    total_width = driver.execute_script("return document.body.offsetWidth")
    total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")

    stitched_image = Image.new("RGB", (total_width, total_height))

    height_remaining = total_height
    for part in range(0, int(total_height / viewport_height) + 1):
        scroll_height = part * viewport_height
        driver.execute_script(f"window.scrollTo(0, {scroll_height})")
        file_name = f"{tmpdir}/part_{part}.png"

        driver.get_screenshot_as_file(file_name)
        screenshot = Image.open(file_name)
        if screenshot.height > height_remaining:
            screenshot = screenshot.crop(
                (
                    0,
                    screenshot.height - height_remaining,
                    screenshot.width,
                    screenshot.height,
                )
            )

        offset = part * viewport_height
        stitched_image.paste(screenshot, (0, offset))

        height_remaining = height_remaining - screenshot.height
        del screenshot
        os.remove(file_name)

    stitched_image.save(f"{tmpdir}/screenshot.png")


@pytest.fixture
def selenium(driver, website, tmpdir):
    driver.get(website)
    yield driver
    full_screenshot(driver, tmpdir)


def run_command_in_container(container_id, command):
    process = subprocess.run(
        f"docker exec -u root {container_id} {command}", shell=True, capture_output=True
    )
    return process.returncode, process.stdout.decode()


@pytest.fixture
def download_dir(request, selenium_data_path):
    outputs_path = f"{request.config.rootdir}/data/downloads"
    os.makedirs(outputs_path, exist_ok=True)
    # mode change needed for selenium to write downloads there:
    os.chmod(outputs_path, 0o777)

    yield outputs_path

    # cleanup requires workarounds...
    # if selenium is run inside container, then downloaded file file has different file owner
    # than process running tests. The workaround is to run rm in running container.
    container_details = subprocess.run(
        "docker container ls --all | grep 'selenium/standalone-firefox.*tests_firefox_[0-9]\+'",
        shell=True, capture_output=True
    )
    if container_details.returncode == 0:
        container_id = container_details.stdout.decode().split(" ", 1)[0]
        run_command_in_container(container_id, f"rm -rf {selenium_data_path}/downloads")
    else:
        shutil.rmtree(outputs_path)
