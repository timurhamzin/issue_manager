import os
from datetime import datetime
from typing import Optional, Union

from fastapi import HTTPException

from config.config import match_breadcrumbs_to_tracker_fields, ISSUE_URL, TRACKER_CHECKLIST_ISSUE_ID
from utils.log import LoggerUtils
from utils.pierce_api import preprocess_url, postprocess_fetched_data
from utils.tracker import patch_tracker_issue


async def process_and_update_issue(issue, issue_patch_url, issue_field_keys, response_data):
    from main import browser_manager
    api_url = preprocess_url(issue.link)
    result = await browser_manager.fetch_from_external_api_async(api_url, url_source='patch_issue_fields')
    error_count = len(response_data['errors'])
    data = await postprocess_fetched_data(
        browser_manager, api_url, result, issue=issue, checklist_error_messages=response_data['errors'])
    postprocessed_success = len(response_data['errors']) == error_count

    # Map breadcrumb fields to tracker fields
    tracker_fields, unset_field_keys = match_breadcrumbs_to_tracker_fields(data, issue_field_keys)

    # Issue PATCH requests to update tracker fields
    for field_key, field_value in tracker_fields.items():
        patch_data = {field_key: field_value}
        patch_response = await patch_tracker_issue(issue_patch_url, patch_data)
        if patch_response.status_code != 200:
            err_context = dict(**patch_data)
            raise LoggerUtils(__name__).create_exception(
                err_code='failed_to_patch_issue_field',
                err_type=HTTPException,
                err_kwargs={'status_code': patch_response.status_code},
                log=True, **err_context)

    if postprocessed_success:
        # After successfully patching the issue fields, mark the checklist item as checked
        await set_listitem_done_status(checklist_item_id=issue.checklist_item_id, done=True, deadline_datetime=datetime.now())
        issue.done = True

    response_data[issue_patch_url] = data


async def set_listitem_done_status(checklist_item_id, done: bool, deadline_datetime: Optional[Union[str, datetime]] = None):
    """Checks or unchecks the issue item in the tracker,
    and mutates its `done` attribute if the status change was successful.
    If `deadline_datetime` is defaulted, it'll be left unchanged.
    """
    checklist_issue_url = ISSUE_URL.format(issue_id=TRACKER_CHECKLIST_ISSUE_ID)
    checklist_item_url = f"{checklist_issue_url}/checklistItems/{checklist_item_id}/"
    checklist_patch_data = {
        "checked": done,
    }
    if deadline_datetime:
        if isinstance(deadline_datetime, datetime):
            deadline_datetime = deadline_datetime.isoformat(timespec='milliseconds') + '+0000'
        checklist_patch_data.update({
            "deadline": {
                "date": deadline_datetime,
                "deadlineType": "date"
            }
        })
    checklist_patch_response = await patch_tracker_issue(checklist_item_url, checklist_patch_data)
    if checklist_patch_response.status_code != 200:
        raise LoggerUtils(__name__).create_exception(
            err_code='failed_to_patch_issue_field',
            err_type=HTTPException,
            err_kwargs={'status_code': checklist_patch_response.status_code},
            checklist_item_url=checklist_item_url)
    return checklist_item_url, checklist_patch_response


async def handle_issue_processing_error(exception, issue, issue_patch_url, response_data):
    error_msg = LoggerUtils(__name__).log(
        msg_or_err_code=str(exception), level=LoggerUtils.levels.ERROR, e=exception,
        issue_id=issue.key, issue_link=issue.link)
    checklist_item_url = f'{issue_patch_url}/checklistItems/{issue.checklist_item_id}/'
    error_patch_data = {os.getenv('TRACKER_BREADCRUMBS_ERROR_KEY'): error_msg}
    response_data['errors'].append((issue.key, error_msg))
    await patch_tracker_issue(checklist_item_url, error_patch_data)
