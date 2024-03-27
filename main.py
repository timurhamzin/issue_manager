import asyncio
import logging
import sys

import structlog
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader

from api import process_checklist
from config.config import (
    API_KEY_NAME, API_KEY_VALUE, BROWSER_START_URL, BROWSER_START_URL_LOADING_ELEMENT_SELECTOR,
    DRIVER_INITIALIZATION_TIMEOUT,
    BROWSER_DOWNLOAD_DIRECTORY, TEST_FETCH_BREADCRUMBS_URL, get_settings, update_settings, TRACKER_CHECKLIST_ISSUE_ID,
    TRACKER_BREADCRUMBS_ERROR_KEY, DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME, get_settings_sync, ConfigModel)
from utils.browser_manager import BreadcrumbsBrowserManager
from utils.log import LoggerUtils, LastLogSafeCaptureProcessor, \
    last_log_safe_capture_processor
from utils.process_issue import set_listitem_done_status
from utils.tracker import get_issue, process_checklist_items

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        last_log_safe_capture_processor,
        structlog.processors.KeyValueRenderer(key_order=['event', 'browser', 'port']),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

browser_manager = BreadcrumbsBrowserManager(
    start_url=BROWSER_START_URL,
    loading_element_selector=BROWSER_START_URL_LOADING_ELEMENT_SELECTOR,
    driver_initialization_timeout=DRIVER_INITIALIZATION_TIMEOUT,
    browser_download_dir=BROWSER_DOWNLOAD_DIRECTORY,
    test_fetch_from_external_api_url=TEST_FETCH_BREADCRUMBS_URL)

app = FastAPI()


@app.middleware("http")
async def log_errors(request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        LoggerUtils(__name__).log(str(e), level=LoggerUtils.levels.ERROR, e=e)
        raise


async def process_checklist_continuously():
    while True:
        config = await get_settings()
        await process_checklist()
        await asyncio.sleep(config['process_checklist_frequency_seconds'])


async def get_api_key(api_key_header: str = Depends(api_key_header)):
    if api_key_header == API_KEY_VALUE:
        return api_key_header
    else:
        raise LoggerUtils(__name__).create_exception(
            err_code='invalid_api_key',
            err_type=HTTPException,
            err_kwargs={'status_code': 403},
            api_key_header=api_key_header)


@app.post('/set_settings', dependencies=[Depends(get_api_key)])
async def set_settings(new_settings: ConfigModel):
    last_settings = (await get_settings()).copy()
    await update_settings(new_settings.model_dump())
    current_settings = await get_settings()
    if current_settings != last_settings:
        result = {"message": LoggerUtils(__name__).log(
            'settings_updated_successfully', level=LoggerUtils.levels.INFO, config=new_settings.model_dump(),
            info='Checklist processing was triggered')}
    else:
        result = {"message": LoggerUtils(__name__).log(
            'no_settings_change_detected', level=LoggerUtils.levels.INFO, config=new_settings.model_dump())}
    await process_checklist()
    return result


@app.get('/get_settings', dependencies=[Depends(get_api_key)])
async def get_settings_endpoint():
    settings = await get_settings()
    return settings


@app.post('/uncheck_deferred_issues_with_clean_error_field', dependencies=[Depends(get_api_key)])
async def uncheck_deferred_issues_with_clean_error_field():
    checklist_issue = await get_issue(TRACKER_CHECKLIST_ISSUE_ID)
    checked_items = []
    unchecked_items = []
    errors = []

    for checklist_item in checklist_issue.checklistItems:
        try:
            issue = await get_issue(checklist_item.text)
        except HTTPException as e:
            error_message = (
                'Issue could not be retrieved, probably because the listitem text '
                'does not match any existing issue name. '
                'The issue will be checked to prevent further processing.')
            LoggerUtils(__name__).log(
                'ERROR_GETTING_ISSUE',
                level=LoggerUtils.levels.ERROR,
                checklist_item__text=checklist_item.text,
                checklist_item__id=checklist_item.id,
                message=error_message
            )
            errors.append({
                'checklist_item_id': checklist_item.id,
                'checklist_item_text': checklist_item.text,
                'error_message': error_message
            })
            if not checklist_item.checked:
                await set_listitem_done_status(
                    checklist_item_id=checklist_item.id, done=True,
                    deadline_datetime=DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME
                )
                checked_items.append({
                    'checklist_item_id': checklist_item.id,
                    'checklist_item_text': checklist_item.text,
                })
            continue

        error_field_value = getattr(issue, TRACKER_BREADCRUMBS_ERROR_KEY)

        if not error_field_value and checklist_item.deadline and checklist_item.deadline.date >= DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME:
            # Uncheck the issue in the checklist
            checklist_item_url, checklist_patch_response = await set_listitem_done_status(
                checklist_item_id=checklist_item.id, done=False
            )
            LoggerUtils(__name__).log(
                'issue_unchecked_successfully',
                level=LoggerUtils.levels.INFO,
                issue_id=checklist_item.text,
                checklist_item_url=checklist_item_url
            )
            unchecked_items.append({
                'checklist_item_id': checklist_item.id,
                'checklist_item_text': checklist_item.text,
                'checklist_item_url': checklist_item_url
            })

    return {
        'unchecked_items': unchecked_items,
        'errors': errors
    }


@app.post('/process_checklist_now', dependencies=[Depends(get_api_key)])
async def process_checklist_now():
    return await process_checklist()


async def uncheck_deferred_issues_continuously():
    while True:
        config = await get_settings()
        await uncheck_deferred_issues_with_clean_error_field()
        await asyncio.sleep(config['uncheck_deferred_issues_frequency_seconds'])


@app.on_event("startup")
async def startup():
    asyncio.create_task(process_checklist_continuously())
    asyncio.create_task(uncheck_deferred_issues_continuously())
