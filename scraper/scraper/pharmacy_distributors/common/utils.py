import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException


def check_webdriver_is_present():
    try:
        # Specify the path if it's not added to PATH
        # driver = webdriver.Chrome(executable_path="/path/to/chromedriver")
        driver = webdriver.Chrome(get_browser_options())
        driver.get("http://www.google.com")
        logging.info("ChromeDriver is available and functional.")
        driver.quit()
    except WebDriverException as e:
        logging.exception("Error with ChromeDriver: ", e)
        raise e


def get_browser_options() -> Options:
    options = Options()
    options.add_argument("--headless")  # Ensure GUI is off
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    options.add_argument("--disable-gpu")  # Applicable to Windows environments
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=9222")  # Enable remote debugging

    return options
