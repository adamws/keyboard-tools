import pytest

from selenium.webdriver.common.by import By


@pytest.mark.parametrize(
    "index,xpath",
    [
        (1, "//button[normalize-space(.)='Upload layout']"),
        (2, "//p[contains(text(), 'All tools on this site')]"),
    ],
)
def test_navigation_bar(index, xpath, selenium):
    navigation_bar = selenium.find_element("xpath", "//ul[@role='menubar']")
    navigation_items = navigation_bar.find_elements(By.TAG_NAME, "li")
    navigation_items[index].click()
    assert selenium.find_element("xpath", xpath)


@pytest.mark.parametrize(
    "selenium,xpath",
    [
        ("/kle-converter", "//button[normalize-space(.)='Upload layout']"),
        ("/about", "//p[contains(text(), 'All tools on this site')]"),
    ], indirect=["selenium"],
)
def test_direct_path(selenium, xpath):
    assert selenium.find_element("xpath", xpath)

