from config.config import (
    ISSUE_URL, load_issue_field_keys, TRACKER_CHECKLIST_ISSUE_ID, get_settings, DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME)
from models import ProcessIssueRequest
from utils.log import LoggerUtils
from utils.process_issue import process_and_update_issue, set_listitem_done_status
from utils.tracker import (
    get_issue, process_checklist_items, clear_error_field, delete_tracker_issue,
    report_aggregated_errors)
from utils.utils import ErrorList


# @app.get("/process_checklist")
async def process_checklist():
    # Initial setup: clear errors and fetch issues
    checklist_issue_url = ISSUE_URL.format(issue_id=TRACKER_CHECKLIST_ISSUE_ID)
    await clear_error_field(checklist_issue_url)
    checklist_issue = await get_issue(TRACKER_CHECKLIST_ISSUE_ID)

    # Process each checklist item
    checked_items, unchecked_items, checklist_error_messages = await process_checklist_items(checklist_issue)

    # Patch issues and handle any errors
    issues_request_data = ProcessIssueRequest(issues=unchecked_items)
    response = await process_issues(issues_request_data)
    response['ignored_issues'] = checked_items
    checklist_error_messages.extend(response.get('errors', []))

    # Accumulate and log errors at the end
    if checklist_error_messages:
        await report_aggregated_errors(checklist_error_messages)

    return response


# @app.patch("/process_issues/")
async def process_issues(request: ProcessIssueRequest):
    config = await get_settings()
    issue_field_keys = load_issue_field_keys()
    response_data = {'errors': ErrorList(), 'processed_issues': []}
    for issue in request.issues:
        issue_patch_url = ISSUE_URL.format(issue_id=issue.key)
        await clear_error_field(issue_patch_url)
        try:
            # Process fetched data and update tracker fields
            await process_and_update_issue(issue, issue_patch_url, issue_field_keys, response_data)

            response_data['processed_issues'].append({'key': issue.key, 'link': issue.link})

        except Exception as e:
            error_msg = LoggerUtils(__name__).log(
                msg_or_err_code=str(e), level=LoggerUtils.levels.ERROR, e=e,
                issue_id=issue.key, issue_link=issue.link)
            await response_data['errors'].append((issue.key, error_msg))
        finally:
            if issue.done:
                # The issue was successfully processed.
                if config['delete_done_checklist_items']:
                    checklist_issue_url = ISSUE_URL.format(issue_id=TRACKER_CHECKLIST_ISSUE_ID)
                    checklist_item_url = f'{checklist_issue_url}/checklistItems/{issue.checklist_item_id}/'
                    await delete_tracker_issue(checklist_item_url)
            else:
                # Checking issue as done here means it was processed
                # and will not be scheduled for processing until unchecked.
                # The date is set to a future date to indicate there was
                # an issue processing it.
                await set_listitem_done_status(checklist_item_id=issue.checklist_item_id, done=True, deadline_datetime=DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME)
                issue.done = True

    return response_data
