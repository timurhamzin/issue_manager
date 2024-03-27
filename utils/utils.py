from http import HTTPStatus
from typing import Union

from dotenv import load_dotenv
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.webdriver import WebDriver as EdgeDriver
from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver
from selenium.webdriver.ie.webdriver import WebDriver as IEDriver
from selenium.webdriver.remote.webdriver import WebDriver as RemoteDriver
from selenium.webdriver.safari.webdriver import WebDriver as SafariDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.webkitgtk.webdriver import WebDriver as WebkitGTKDriver
from selenium.webdriver.wpewebkit.webdriver import WebDriver as WPEWebKitDriver

from utils.log import LoggerUtils

WebDriverUnion = Union[
    ChromeDriver,
    EdgeDriver,
    FirefoxDriver,
    IEDriver,
    RemoteDriver,
    SafariDriver,
    WebkitGTKDriver,
    WPEWebKitDriver
]

load_dotenv()


def str2bool(value):
    if value is None:
        return None
    elif isinstance(value, bool):
        return value
    elif isinstance(value, str):
        value = value.strip().lower()
        if value in ('true', 'yes', 'on', '1'):
            return True
        elif value in ('false', 'no', 'off', '0'):
            return False
        else:
            return None
    else:
        return None


def load_page_fully(driver, url, timeout_secs=10, loading_element_selector=".loading"):
    driver.get(url)

    # Wait for the readyState to be complete
    WebDriverWait(driver, timeout_secs).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )

    # Wait for AJAX calls to complete (jQuery example)
    # Note: Only include this line if the website uses jQuery for AJAX calls.
    # WebDriverWait(driver, timeout_secs).until(
    #     lambda d: d.execute_script('return jQuery.active == 0')
    # )

    # Wait for the absence of the loading indicator
    WebDriverWait(driver, timeout_secs).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, loading_element_selector))
    )


class ThreadResult:
    def __init__(self):
        self.data = None
        self.exception = None
        self.exc_type = None
        self.exc_traceback = None
        self.exc_message = None
        self.exc_detail = None


def exception_to_str(e: Exception):
    return f'Exception `{type(e).__name__}: {e}`.'


def convert_http_exception_to_error_code(http_exception):
    status_code = http_exception.status_code
    error_code = HTTPStatus(status_code).phrase.replace(' ', '_')
    return error_code


class ErrorList(list):
    async def append(self, item):
        """
        Overrides the append method to report an individual issue error
        when a new error is added to the list.
        """
        super().append(item)  # Call the superclass method to actually append the item
        if isinstance(item, tuple) and len(item) == 2:
            issue, error = item
            from utils.tracker import report_individual_issue_error
            await report_individual_issue_error(issue, error)
        else:
            raise LoggerUtils(__name__).create_exception(
                'illegal_errorlist_item', ValueError,
                message='Items appended to ErrorList must be 2-tuple of strings (issue, error).',
                item=str(item))
