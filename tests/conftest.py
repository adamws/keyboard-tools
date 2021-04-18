import base64
import os
import pytest
import subprocess

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
def selenium_session(selenium_data_path):
    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.download.dir", f"{selenium_data_path}/downloads")
    selenium = webdriver.Remote(
        command_executor='http://localhost:4444/wd/hub',
        options=options
    )
    yield selenium
    selenium.quit()


@pytest.fixture
def selenium(selenium_session, website, tmpdir):
    selenium_session.get(website)
    yield selenium_session
    selenium_session.save_screenshot(f"{tmpdir}/screenshot.png")


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
    # if selenium is run inside container, then downloaded png file has different file owner
    # than process running tests. The workaround is to run rm in running container.
    container_details = subprocess.run(
        "docker container ls --all | grep tests_firefox", shell=True, capture_output=True
    )
    if container_details.returncode == 0:
        container_id = container_details.stdout.decode().split(" ", 1)[0]
        run_command_in_container(container_id, f"rm -rf {selenium_data_path}/downloads")
    else:
        shutil.rmtree(outputs_path)
