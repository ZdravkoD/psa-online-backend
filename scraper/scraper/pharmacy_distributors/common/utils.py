import logging
from selenium import webdriver
from selenium.common.exceptions import WebDriverException


def check_webdriver_is_present():
    try:
        # Specify the path if it's not added to PATH
        # driver = webdriver.Chrome(executable_path="/path/to/chromedriver")
        driver = webdriver.Chrome()
        driver.get("http://www.google.com")
        logging.info("ChromeDriver is available and functional.")
        driver.quit()
    except WebDriverException as e:
        logging.exception("Error with ChromeDriver: ", e)
        raise e
