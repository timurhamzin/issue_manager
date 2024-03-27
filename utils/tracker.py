import json
import os
from typing import Tuple, List

import httpx
from fastapi import HTTPException

from config.config import (
    ISSUE_URL, TRACKER_CHECKLIST_ISSUE_ID, TRACKER_PATCH_TIMEOUT)
from models import IssueModel, IssueData
from utils.log import LoggerUtils


async def delete_tracker_issue(url):
    import httpx

    headers = {'Authorization': f'Bearer {os.getenv("TRACKER_OAUTH_TOKEN")}'}
    async with httpx.AsyncClient() as client:
        return await client.delete(url, headers=headers)


async def patch_tracker_issue(url, data):
    import httpx

    headers = {'Authorization': f'Bearer {os.getenv("TRACKER_OAUTH_TOKEN")}'}
    timeout = TRACKER_PATCH_TIMEOUT
    async with httpx.AsyncClient() as client:
        try:
            return await client.patch(url, json=data, headers=headers,
                                      timeout=timeout)
        except Exception as e:
            # patch errors are logged without being saved in tracker to prevent circular failures.
            LoggerUtils(__name__).log(
                'patch_tracker_issue_error', level=LoggerUtils.levels.ERROR,
                url=url, json=data, timeout=timeout, original_exception=e)


async def get_issue(issue_id: str) -> IssueModel:
    headers = {'Authorization': f"Bearer {os.getenv('TRACKER_OAUTH_TOKEN')}"}
    url = ISSUE_URL.format(issue_id=issue_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    if response.status_code != 200:
        raise LoggerUtils(__name__).create_exception(
            'tracker_checklist_retrieval_error',
            HTTPException,
            err_kwargs=dict(status_code=response.status_code),
            url=url
        )
    try:
        issue = IssueModel.model_validate_json(response.text)
        return issue
    except Exception as e:
        raise LoggerUtils(__name__).create_exception(
            'issue_parsing_error',
            HTTPException,
            original_exception=e,
            err_kwargs=dict(status_code=response.status_code),
            url=url
        )


async def process_checklist_items(checklist_issue) -> Tuple[
    List[dict], List[IssueData], List[Tuple[str, str]]]:
    checked_items = []
    unchecked_items = []
    checklist_error_messages = []
    for checklist_item in checklist_issue.checklistItems:
        try:
            if checklist_item.checked:
                checked_items.append(
                    {'key': checklist_item.text, 'id': checklist_item.id})
            else:
                individual_issue = await get_issue(checklist_item.text)
                link = getattr(individual_issue, os.getenv('TRACKER_LINK_KEY'),
                               None)
                if link is None:
                    error_msg = LoggerUtils(__name__).log(
                        'link_is_not_set_for_issue',
                        level=LoggerUtils.levels.ERROR,
                        issue_id=checklist_item.text)
                    error_patch_data = {
                        os.getenv('TRACKER_BREADCRUMBS_ERROR_KEY'): error_msg
                    }
                    tracker_issue_patch_url = ISSUE_URL.format(
                        issue_id=checklist_item.text)
                    await patch_tracker_issue(tracker_issue_patch_url,
                                              error_patch_data)
                    checklist_error_messages.append(
                        (checklist_item.text, error_msg))

                    continue

                issue_data = IssueData(link=link, key=checklist_item.text,
                                       checklist_item_id=checklist_item.id)
                unchecked_items.append(issue_data)
        except Exception as e:
            error_msg = LoggerUtils(__name__).log(
                'checklist_item_processing_error',
                level=LoggerUtils.levels.ERROR, e=e,
                checklist_item_id=checklist_item.id, issue=checklist_item.text)
            checklist_error_messages.append((checklist_item.text, error_msg))

            continue

    return checked_items, unchecked_items, checklist_error_messages


async def clear_error_field(issue_patch_url):
    await patch_tracker_issue(issue_patch_url,
                              {os.getenv('TRACKER_BREADCRUMBS_ERROR_KEY'): ''})


async def report_individual_issue_error(issue, error):
    """
    Reports an error on the issue that caused it.
    """
    error_field_data = {
        os.getenv('TRACKER_BREADCRUMBS_ERROR_KEY'): json.dumps(error)
    }
    issue_url = ISSUE_URL.format(issue_id=issue)
    await patch_tracker_issue(issue_url, error_field_data)


async def report_aggregated_errors(checklist_error_messages):
    """
    Reports an aggregated error on the checklist issue.
    """
    issues_vs_errors = {issue: error for issue, error in
                        checklist_error_messages}

    accumulated_error_msg = json.dumps(issues_vs_errors)
    error_field_data = {
        os.getenv('TRACKER_BREADCRUMBS_ERROR_KEY'): accumulated_error_msg
    }
    checklist_issue_url = ISSUE_URL.format(issue_id=TRACKER_CHECKLIST_ISSUE_ID)
    await patch_tracker_issue(checklist_issue_url, error_field_data)
