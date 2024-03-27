import ast
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from utils.log import LoggerUtils
from utils.utils import str2bool

load_dotenv()

try:
    BROWSER_START_URL = os.environ['BROWSER_START_URL']
    BROWSER_START_URL_LOADING_ELEMENT_SELECTOR = os.environ['BROWSER_START_URL_LOADING_ELEMENT_SELECTOR']
    DRIVER_INITIALIZATION_TIMEOUT = int(os.environ['DRIVER_INITIALIZATION_TIMEOUT'])
    TRACKER_PATCH_TIMEOUT = int(os.environ['TRACKER_PATCH_TIMEOUT'])
    BROWSER_DOWNLOAD_DIRECTORY = os.environ['BROWSER_DOWNLOAD_DIRECTORY']
    TEST_FETCH_BREADCRUMBS_URL = os.environ['TEST_FETCH_BREADCRUMBS_URL']
    API_KEY_NAME = os.environ['API_KEY_NAME']
    API_KEY_VALUE = os.environ['API_KEY_VALUE']
    ISSUE_URL = os.environ['ISSUE_URL']
    TEST_URLS_STR = os.environ['TEST_URLS']
    TRACKER_CHECKLIST_ISSUE_ID = os.environ['TRACKER_CHECKLIST_ISSUE_ID']
    TRACKER_LINK_KEY = os.environ['TRACKER_LINK_KEY']
    TRACKER_BREADCRUMBS_ERROR_KEY = os.environ['TRACKER_BREADCRUMBS_ERROR_KEY']
    DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME = os.environ['DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME']
    DEBUGGING_BROWSER_PORT = int(os.getenv('DEBUGGING_BROWSER_PORT'))

    BROWSER_TYPE = os.getenv('BROWSER_TYPE', 'chrome').lower()
    BROWSER_PROCESS_NAME = os.getenv('BROWSER_PROCESS_NAME', 'chrome').lower()
    BROWSER_PATH = os.getenv('BROWSER_PATH')
    RUN_BROWSER_LOCALLY = str2bool(os.environ.get('RUN_BROWSER_LOCALLY'))
    ROOT_DIR = Path(__file__).parent.parent
    if os.path.exists(os.getenv('DRIVER_SERVICE')):
        DRIVER_SERVICE = os.getenv('DRIVER_SERVICE')
    else:
        DRIVER_SERVICE = ROOT_DIR / os.getenv('DRIVER_SERVICE')
        if not os.path.exists(DRIVER_SERVICE):
            raise LoggerUtils(__name__).create_exception(
                'driver_service_not_found', FileNotFoundError, DRIVER_SERVICE=DRIVER_SERVICE)
except ValueError as e:
    raise LoggerUtils(__name__).create_exception(
        'required_environment_variable_is_unset', ValueError, original_exception=e)


def load_issue_field_keys():
    return {
        'TRACKER_TASK_POSITION_IF_EXISTS_KEY': os.getenv('TRACKER_TASK_POSITION_IF_EXISTS_KEY'),
        'TRACKER_TASK_POSITION_KEY': os.getenv('TRACKER_TASK_POSITION_KEY'),
        'TRACKER_MODULE_NAME_KEY': os.getenv('TRACKER_MODULE_NAME_KEY'),
        'TRACKER_TRACK_NAME_KEY': os.getenv('TRACKER_TRACK_NAME_KEY'),
        'TRACKER_TRACK_ID_KEY': os.getenv('TRACKER_TRACK_ID_KEY'),
        'TRACKER_LESSON_NAME_KEY': os.getenv('TRACKER_LESSON_NAME_KEY'),
        'TRACKER_SPRINT_NAME_KEY': os.getenv('TRACKER_SPRINT_NAME_KEY'),
        'TRACKER_SPRINT_ID_KEY': os.getenv('TRACKER_SPRINT_ID_KEY'),
        'TRACKER_TOPIC_NAME_KEY': os.getenv('TRACKER_TOPIC_NAME_KEY'),
        'TRACKER_FACULTY_NAME_KEY': os.getenv('TRACKER_FACULTY_NAME_KEY'),
        'TRACKER_PROFESSION_NAME_KEY': os.getenv('TRACKER_PROFESSION_NAME_KEY'),
        'BREADCRUMBS_TASK_POSITION_IF_EXISTS_KEY': os.getenv('BREADCRUMBS_TASK_POSITION_IF_EXISTS_KEY'),
        'BREADCRUMBS_TASK_POSITION_KEY': os.getenv('BREADCRUMBS_TASK_POSITION_KEY'),
        'BREADCRUMBS_MODULE_NAME_KEY': os.getenv('BREADCRUMBS_MODULE_NAME_KEY'),
        'BREADCRUMBS_TRACK_NAME_KEY': os.getenv('BREADCRUMBS_TRACK_NAME_KEY'),
        'BREADCRUMBS_TRACK_ID_KEY': os.getenv('BREADCRUMBS_TRACK_ID_KEY'),
        'BREADCRUMBS_LESSON_NAME_KEY': os.getenv('BREADCRUMBS_LESSON_NAME_KEY'),
        'BREADCRUMBS_SPRINT_NAME_KEY': os.getenv('BREADCRUMBS_SPRINT_NAME_KEY'),
        'BREADCRUMBS_SPRINT_ID_KEY': os.getenv('BREADCRUMBS_SPRINT_ID_KEY'),
        'BREADCRUMBS_TOPIC_NAME_KEY': os.getenv('BREADCRUMBS_TOPIC_NAME_KEY'),
        'BREADCRUMBS_FACULTY_NAME_KEY': os.getenv('BREADCRUMBS_FACULTY_NAME_KEY'),
        'BREADCRUMBS_PROFESSION_NAME_KEY': os.getenv('BREADCRUMBS_PROFESSION_NAME_KEY'),
    }


def match_breadcrumbs_to_tracker_fields(breadcrumbs, config):
    """
    Match breadcrumb keys to tracker fields using the configuration and return
    tracker fields and unused config items.
    """
    tracker_fields = {}
    used_config_keys = set()  # Track which config keys are used

    for breadcrumb_category, breadcrumb_values in breadcrumbs.items():
        for key, value in breadcrumb_values.items():
            breadcrumb_key = f"{breadcrumb_category}.{key}"
            for config_key, config_value in config.items():
                if config_value == breadcrumb_key:
                    tracker_key = config_key.replace('BREADCRUMBS_', 'TRACKER_')
                    tracker_fields[config[tracker_key]] = value
                    used_config_keys.update([config_key, tracker_key])
    unused_config_items = {key: value for key, value in config.items() if key not in used_config_keys}

    return tracker_fields, unused_config_items


if TEST_URLS_STR:
    try:
        test_urls = ast.literal_eval(TEST_URLS_STR)  # Safely convert the string to a list
    except (SyntaxError, ValueError) as e:
        raise LoggerUtils(__name__).create_exception(
            'error_test_urls_value', ValueError, log=True,
            detail='Invalid format of TEST_URLS in the .env file. Use python list syntax.')
    else:
        if not test_urls:
            raise LoggerUtils(__name__).create_exception(
                "error_test_urls_value", ValueError, log=True,
                detail='Invalid value of TEST_URLS in the .env file. Set it to a url or a list of urls in python syntax.')

SETTINGS_PATH = Path('config') / 'settings.json'

with open(SETTINGS_PATH, 'r', encoding='utf-8') as file:
    settings = json.load(file)


async def get_settings() -> dict:
    return settings


def get_settings_sync() -> dict:
    return settings


async def update_settings(new_settings) -> None:
    settings.update(new_settings)


class ConfigModel(BaseModel):
    process_checklist_frequency_seconds: int = Field(default=settings.get('process_checklist_frequency_seconds', 30),
                                                     gt=0, le=60 * 60 * 24)
    uncheck_deferred_issues_frequency_seconds: int = Field(
        default=settings.get('uncheck_deferred_issues_frequency_seconds', 60), gt=0, le=60 * 60 * 24)
    delete_done_checklist_items: bool = settings.get('delete_done_checklist_items', False)
    modify_browser_page_on_fetch: bool = settings.get('modify_browser_page_on_fetch', False)
    ignore_errors: dict = Field(default=settings['ignore_errors'])
