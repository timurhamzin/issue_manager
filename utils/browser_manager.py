import asyncio
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import traceback
import uuid
from queue import Queue, Empty
from threading import Thread, Lock
from typing import Union

import aiofiles
import psutil
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from config.config import get_settings_sync, get_settings, DRIVER_SERVICE, \
    DEBUGGING_BROWSER_PORT, BROWSER_TYPE, BROWSER_PATH, RUN_BROWSER_LOCALLY, \
    BROWSER_PROCESS_NAME
from utils.log import LoggerUtils
from utils.pierce_api import preprocess_url
from utils.utils import str2bool, ThreadResult

load_dotenv()


class BrowserManager:
    def __init__(self, start_url: str, loading_element_selector: str,
                 driver_initialization_timeout: int):
        self.browser_path = BROWSER_PATH
        self.browser_type = BROWSER_TYPE
        self.browser_process_name = BROWSER_PROCESS_NAME
        self.run_browser_locally = RUN_BROWSER_LOCALLY
        self.debugging_browser_port = DEBUGGING_BROWSER_PORT

        self.driver_initialization_timeout = driver_initialization_timeout
        self.start_url = start_url
        self.loading_element_selector = loading_element_selector
        self._driver = None
        self._driver_lock = Lock()

    def _is_page_responsive(self, raise_if_irresponsive=False) -> bool:
        """
        Synchronous method to check if a page is responsive.
        Override in the subclass with specific logic.
        """
        # This method should be implemented in the subclass.
        raise NotImplementedError

    def get_driver(self) -> WebDriver:
        with self._driver_lock:
            if self._driver:
                if not self._is_page_responsive():
                    try:
                        self._driver.close()
                    except Exception as e:
                        LoggerUtils(__name__).log('driver_close_error', level=LoggerUtils.levels.ERROR, e=e)
                    self._driver = None

            if not self._driver:
                self._initialize_driver()

            return self._driver

    def _get_driver_in_thread(self, driver_service, options):
        driver_queue = Queue()
        driver_thread = Thread(target=self._init_driver, args=(driver_queue, driver_service, options))
        driver_thread.start()

        try:
            return (driver_queue.get(timeout=self.driver_initialization_timeout), driver_thread)
        except Empty as e:
            LoggerUtils(__name__).log('timeout_getting_driver', level=LoggerUtils.levels.ERROR, e=e)
            return (None, driver_thread)

    def _initialize_driver(self):
        if self._driver:
            try:
                self._driver.close()
            except Exception as e:
                LoggerUtils(__name__).log(msg_or_err_code='driver_close_error', level=LoggerUtils.levels.ERROR, e=e)
            finally:
                self._driver = None
        LoggerUtils(__name__).log('initializing_driver', level=LoggerUtils.levels.INFO)
        options = self._get_browser_options(self.browser_type)
        if self.run_browser_locally:
            if self.browser_type not in ['chromium', 'chrome']:
                raise LoggerUtils(__name__).create_exception('browser_type_not_supported', NotImplementedError, log=True, BROWSER_TYPE=BROWSER_TYPE)
            if not self._is_browser_running():
                self._start_browser()
            driver_service = Service(executable_path=DRIVER_SERVICE)
            (self._driver, thread_to_get_driver) = self._get_driver_in_thread(driver_service, options)
            if not self._driver or not self._is_page_responsive():
                self._kill_browser_processes()
                self._start_browser()
                (self._driver, thread_to_get_driver) = self._get_driver_in_thread(driver_service, options)
            if not self._driver:
                raise LoggerUtils(__name__).create_exception('driver_initialization_failure', RuntimeError, log=True)
            else:
                thread_to_get_driver.join()
            self._is_page_responsive(raise_if_irresponsive=True)
        else:
            raise LoggerUtils(__name__).create_exception('configuring_remote_driver_not_implemented', NotImplementedError, log=True, DRIVER_SERVICE=DRIVER_SERVICE)
        LoggerUtils(__name__).log('driver_initialized_successfully', level=LoggerUtils.levels.INFO)
        return self._driver

    def _init_driver(self, driver_queue, driver_service, options):
        try:
            driver = webdriver.Chrome(service=driver_service, options=options, keep_alive=True)
            driver_queue.put(driver)
        except WebDriverException as e:
            LoggerUtils(__name__).log('failed_to_initialize_driver', level=LoggerUtils.levels.ERROR, e=e)
            driver_queue.put(None)
        except Exception as e:
            LoggerUtils(__name__).log('unexpected_error_initializing_driver', level=LoggerUtils.levels.ERROR, e=e)
            driver_queue.put(None)

    def _is_browser_running(self):
        running = False
        try:
            for process in psutil.process_iter(attrs=['name']):
                process_name = process.info['name'].lower()
                if self.browser_process_name in process_name:
                    running = True
                    break
            return running
        except Exception as e:
            LoggerUtils(__name__).log('error_checking_browser_process', level=LoggerUtils.levels.ERROR, e=e)
            return False

    async def _is_debugging_port_open(self):
        cmd = f'netstat -tuln | grep ":{self.debugging_browser_port}"'
        process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
        (stdout, _) = await process.communicate()
        return f':{self.debugging_browser_port}' in stdout.decode()
        # Equivalent bash command for self.remote_debugging_port = 9222:
        # PORT=9222; netstat -tuln | grep ":$PORT" > /dev/null && echo "Port is open" || echo "Port is closed"

    def _kill_browser_processes(self, timeout_secs=10):
        for process in psutil.process_iter(attrs=['name']):
            if self.browser_process_name in process.info['name'].lower():
                LoggerUtils(__name__).log(
                    'killing_browser_process', level=LoggerUtils.levels.INFO, process=process.info['name'])

                try:
                    # Replaced subprocess.run(['kill', '-9', str(process.pid)]) with it's cross-platform equivalent
                    p = psutil.Process(process.pid)
                    p.terminate()  # or p.kill() for force termination
                except psutil.NoSuchProcess:
                    LoggerUtils(__name__).log('process_not_found',
                                              level=LoggerUtils.levels.INFO,
                                              process_id=process.pid)
                except Exception as e:
                    exc_context = {
                        'process_id': process.pid, 'error_message': str(e)
                    }
                    raise LoggerUtils(__name__).create_exception(
                        'process_termination_failed', RuntimeError,
                        original_exception=e, **exc_context)

                # Waiting for the process to terminate
                try:
                    process.wait(timeout=timeout_secs)
                except psutil.TimeoutExpired:
                    LoggerUtils(__name__).create_exception(
                        'failed_to_kill_browser_process', TimeoutError, log=True,
                        timeout=timeout_secs, process=process.info['name'])

    def _get_browser_options(self, browser_type: str):
        if browser_type == 'firefox':
            return FirefoxOptions()
        elif browser_type == 'edge':
            return EdgeOptions()
        else:  # Default to Chrome
            options = ChromeOptions()
            options.add_argument('--start-maximized')
            # Port kept open after the request is processed
            # to save on the page loading time for the next request
            options.add_experimental_option(
                'debuggerAddress', f'localhost:{DEBUGGING_BROWSER_PORT}')
            return options

    def _start_browser(self):
        """Implemented synchronously, because the app is supposed to have
        a browser instance running."""
        LoggerUtils(__name__).log('starting_browser', level=LoggerUtils.levels.INFO, browser=self.browser_path, port=self.debugging_browser_port)
        cmd = [self.browser_path, '--remote-debugging-port=' + str(self.debugging_browser_port), '--start-maximized', '--disable-infobars', self.start_url]
        platform = sys.platform
        if platform == 'win32':
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        elif platform == 'darwin':
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        else:  # Linux and other Unix-like
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, start_new_session=True)
        if not self._is_browser_running():
            raise LoggerUtils(__name__).create_exception('failed_to_start_browser', RuntimeError, log=True, platform=platform, browser=self.browser_path)

    def _prepare_js_script(self, js_code_to_execute, injection_file='js_injection_funcs.js'):
        """Reads the JS injection file and combines it with the given JS code."""
        with open(injection_file, 'r', encoding='utf-8') as f:
            js_functions = f.read()
        full_script = js_functions + '\n' + js_code_to_execute
        return full_script

    def execute_js_with_injection(
            self, js_code_to_execute, injection_file='js_injection_funcs.js',
            _driver=None, timeout=5
    ):
        """Execute JavaScript synchronously with a timeout."""
        full_script = self._prepare_js_script(js_code_to_execute, injection_file)

        _driver = _driver or self.get_driver()

        # Event for signaling that the script has completed or timed out
        done = threading.Event()

        # Wrapper function to execute the script
        def run_script(thread_result):
            try:
                thread_result.data = _driver.execute_async_script(full_script)
                if thread_result.data and "error" in thread_result.data:
                    raise LoggerUtils(__name__).create_exception(
                        'js_error', RuntimeError, log=True, detail=thread_result.data)
            except Exception as e:
                thread_result.exc_type = str(type(e))
                thread_result.exc_traceback = traceback.format_exc()
                thread_result.exc_message = str(e)
                thread_result.exc_detail = str(getattr(e, 'error_context', ''))
            finally:
                done.set()

        # Start the script in a separate thread
        thread_result = ThreadResult()
        script_thread = threading.Thread(target=run_script, args=(thread_result,))
        script_thread.start()

        # Wait for the script to complete or timeout
        script_thread.join(timeout)
        # Check for exception in thread
        original_exception = None
        if thread_result.exc_type:
            original_exception = LoggerUtils(__name__).create_exception(
                'execute_js_script_timeout', RuntimeError, log=False, detail=thread_result.exc_detail
            )

        if not done.is_set():
            raise LoggerUtils(__name__).create_exception(
                'execute_js_script_timeout', TimeoutError, log=True,
                timeout=timeout, original_exception=original_exception)
        elif original_exception:
            raise original_exception

        # If completed, return the result
        if script_thread.is_alive():
            LoggerUtils(__name__).log('thread_joined_before_js_execution_finished', level=LoggerUtils.levels.WARNING)
        return thread_result.data


class BreadcrumbsBrowserManager(BrowserManager):

    def __init__(self, *args, browser_download_dir: Union[str, pathlib.Path],
                 test_fetch_from_external_api_url: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser_download_dir = browser_download_dir
        self.test_fetch_from_external_api_url = test_fetch_from_external_api_url
        if not all((browser_download_dir, test_fetch_from_external_api_url)):
            LoggerUtils(__name__).create_exception(
                'missing_required_browser_setup_arguments', ValueError, log=True,
                browser_download_dir=browser_download_dir, test_fetch_from_external_api_url=test_fetch_from_external_api_url)

    def _is_page_responsive(self, raise_if_irresponsive=False, _driver=None) -> bool:
        """Leave _driver defaulted to test with self._driver"""
        if not _driver:
            _driver = self._driver
        if not _driver:
            LoggerUtils(__name__).log('driver_is_not_set', level=LoggerUtils.levels.INFO)
            return False
        try:
            current_url = _driver.current_url
        except WebDriverException as e:
            LoggerUtils(__name__).log('driver_error', level=LoggerUtils.levels.ERROR, e=e)
            return False

        if current_url != self.start_url:
            try:
                LoggerUtils(__name__).log('loading_start_url', level=LoggerUtils.levels.INFO)
                _driver.get(self.start_url)
            except WebDriverException as e:
                LoggerUtils(__name__).log('error_loading_start_url', level=LoggerUtils.levels.ERROR, e=e)
                raise
        err_event = 'fetch_from_external_api_test_failed'
        test_url = preprocess_url(self.test_fetch_from_external_api_url)
        try:
            data = self.fetch_from_external_api_sync(url=test_url, url_source='end_to_end_selenium_test', _driver=_driver)
        except (TimeoutError, RuntimeError) as e:
            return False
        test_passed = bool(data)
        if test_passed:
            LoggerUtils(__name__).log('fetch_from_external_api_test_passed', level=LoggerUtils.levels.INFO)
        else:
            if raise_if_irresponsive:
                LoggerUtils(__name__).create_exception(err_event, RuntimeError, log=True)
            else:
                LoggerUtils(__name__).log(err_event, level=LoggerUtils.levels.INFO)
        return test_passed

    def _generate_js_code(self, js_method_name, js_args):
        """
        Generates JavaScript code for given method and arguments.
        """
        unique_filename = str(uuid.uuid4()) + '.json'
        js_args['download_to_filename'] = unique_filename  # Ensure filename is included

        # Handle callback argument
        for predefined_arg in ('callback',):
            if predefined_arg in js_args:
                LoggerUtils(__name__).create_exception('generate_js_code_error', KeyError, log=True, detail='js_arg_is_not_allowed', js_arg=predefined_arg)

        js_args_json = json.dumps(js_args)  # Convert args to JSON string
        js_code = (
            f"var callback = arguments[arguments.length - 1];\n"
            f"var args = {js_args_json};\n"  # Pass the JSON as an object to JS
            f"args['callback'] = callback;\n"
            f"{js_method_name}(args);\n"  # Call the JS function with the args object
        )
        return js_code, unique_filename


    def fetch_from_external_api_sync(self, url: str, url_source: str, _driver=None):
        """Synchronous version to fetch data from an external API.
        url_source is used for logging purposes.
        """
        config = get_settings_sync()
        modify_document = config['modify_browser_page_on_fetch']
        (js_code, unique_filename) = self._generate_js_code('fetchApiUrl', {'apiUrl': url, 'modifyDocument': modify_document})
        try:
            self.execute_js_with_injection(js_code, _driver=_driver)
            self._wait_for_file_sync(os.path.join(self.browser_download_dir, unique_filename))
            with open(os.path.join(self.browser_download_dir, unique_filename), 'r', encoding='utf-8') as fh:
                content = fh.read()
        except RuntimeError as e:
            err_context = dict(url=url, url_source=url_source)
            raise LoggerUtils(__name__).create_exception(
                err_code='error_fetching_breadcrumbs',
                err_type=RuntimeError,
                log=True,
                original_exception=e,
                **err_context
            )
        return self._parse_and_remove_file(unique_filename, content)

    async def fetch_from_external_api_async(self, url: str, url_source: str, _driver=None):
        """Asynchronous version to fetch breadcrumbs.
        url_source is used for logging purposes.
        """
        config = await get_settings()
        modify_document = config['modify_browser_page_on_fetch']
        (js_code, unique_filename) = self._generate_js_code('fetchApiUrl', {'apiUrl': url, 'modifyDocument': modify_document})
        try:
            self.execute_js_with_injection(js_code, _driver=_driver)
            await self._wait_for_file_async(os.path.join(self.browser_download_dir, unique_filename))
            async with aiofiles.open(os.path.join(self.browser_download_dir, unique_filename), 'r',
                                     encoding='utf-8') as fh:
                content = await fh.read()
        except RuntimeError as e:
            err_context = dict(url=url, url_source=url_source)
            raise LoggerUtils(__name__).create_exception(
                err_code='error_fetching_breadcrumbs',
                err_type=RuntimeError,
                log=True,
                original_exception=e,
                **err_context
            )
        return self._parse_and_remove_file(unique_filename, content)

    async def execute_js_method_async(self, js_method_name: str, js_args: dict, _driver=None):
        """Generic method to execute a JavaScript method with any number of arguments."""
        js_code, unique_filename = self._generate_js_code(js_method_name, js_args)

        self.execute_js_with_injection(js_code, _driver=_driver)
        # TODO: add time limit
        await self._wait_for_file_async(os.path.join(self.browser_download_dir, unique_filename))
        async with aiofiles.open(os.path.join(self.browser_download_dir, unique_filename), 'r', encoding='utf-8') as fh:
            content = await fh.read()
        return self._parse_and_remove_file(unique_filename, content)

    async def _wait_for_file_async(self, file_path):
        """Wait for the file to be created (asynchronous)."""
        while not os.path.exists(file_path):
            await asyncio.sleep(0.1)

    def _wait_for_file_sync(self, file_path):
        """Wait for the file to be created (synchronous)."""
        while not os.path.exists(file_path):
            time.sleep(0.1)

    def _parse_and_remove_file(self, filename, content):
        """Parse JSON content and remove the file."""
        data = json.loads(content)
        os.remove(os.path.join(self.browser_download_dir, filename))
        return data
