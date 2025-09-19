import base64
import os
import pytest
import shutil
import subprocess

from pathlib import Path
from PIL import Image
from selenium import webdriver


def pytest_addoption(parser):
    parser.addoption(
        "--webdriver",
        help="Selenium webdriver selection",
        default="remote",
    )
    parser.addoption(
        "--remote-executor",
        help="Address of command executor for remote webdriver",
        default="http://localhost:4444/wd/hub",
    )
    parser.addoption(
        "--website-selenium",
        help="Website address for selenium host",
        default="http://kicad.localhost",
    )
    parser.addoption(
        "--backend-test-host",
        help="Backed address for test host",
        default="http://kicad.localhost",
    )


def is_circleci():
    return "CI" in os.environ


@pytest.fixture(scope="session")
def driver_option(request):
    driver = request.config.getoption("--webdriver")
    if driver != "remote" and driver != "firefox":
        raise ValueError(f"Unsupported --webdriver value: {driver}")
    return driver


@pytest.fixture(scope="session")
def selenium_data_path(driver_option):
    if driver_option == "remote":
        # in container path:
        return "/home/seluser/data"
    return "/tmp/selenium"


@pytest.fixture(scope="session")
def website_selenium(request):
    return request.config.getoption("--website-selenium")


@pytest.fixture(scope="session")
def pcb_endpoint(request):
    value = request.config.getoption("--backend-test-host")
    return f"{value}/api/pcb"


def to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    extras = getattr(report, "extras", [])

    if report.when == "teardown":
        try:
            tmpdir = Path(item.funcargs["tmpdir"])
        except KeyError:
            tmpdir = Path.cwd()
        screenshot_path = tmpdir / "screenshot.png"
        if screenshot_path.is_file():
            encoded = to_base64(screenshot_path)
            extras.append(pytest_html.extras.image(f"data:image/png;base64,{encoded}"))
        report.extras = extras


@pytest.fixture(scope="session")
def driver(request, driver_option, selenium_data_path):
    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.download.dir", f"{selenium_data_path}/downloads")
    if driver_option == "remote":
        _driver = webdriver.Remote(
            command_executor=request.config.getoption("--remote-executor"),
            options=options,
        )
        _driver.set_window_size(1360, 1800)
    else:
        _driver = webdriver.Firefox(options=options)
    #import pdb; pdb.set_trace()
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
def selenium(driver, website_selenium, tmpdir, request):
    path = ""
    try:
        path = request.param
    except AttributeError:
        pass
    driver.get(website_selenium + path)
    yield driver
    full_screenshot(driver, tmpdir)


def run_command_in_container(container_id, command):
    process = subprocess.run(
        f"docker exec -u root {container_id} {command}", shell=True, capture_output=True
    )
    return process.returncode, process.stdout.decode()


@pytest.fixture
def download_dir(request, driver_option, selenium_data_path):
    # returns download directory from host perspective (if runninng in remote container)
    if driver_option == "remote":
        outputs_path = f"{request.config.rootdir}/data/downloads"
        os.makedirs(outputs_path, exist_ok=True)
        # mode change needed for selenium to write downloads there:
        os.chmod(outputs_path, 0o777)

        yield outputs_path

        # cleanup requires workarounds...
        # if selenium is run inside container, then downloaded file file has different file owner
        # than process running tests. The workaround is to run rm in running container.
        container_details = subprocess.run(
            "docker container ls --all | grep 'selenium/standalone-firefox.*tests[-_]firefox[-_][0-9]\+'",
            shell=True,
            capture_output=True,
        )
        if container_details.returncode == 0:
            container_id = container_details.stdout.decode().split(" ", 1)[0]
            run_command_in_container(
                container_id, f"rm -rf {selenium_data_path}/downloads"
            )
        else:
            raise Exception("Could not clean up downloads")
    else:
        outputs_path = f"{selenium_data_path}/downloads"
        yield outputs_path
        shutil.rmtree(outputs_path)
