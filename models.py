from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import create_model
from pydantic.v1 import root_validator

from config.config import (
    TRACKER_LINK_KEY, TRACKER_BREADCRUMBS_ERROR_KEY)


class BreadcrumbRequest(BaseModel):
    url: str


class BreadcrumbsBulkRequest(BaseModel):
    urls: List[str]


class IssueData(BaseModel):
    link: str
    key: str
    checklist_item_id: str
    done: bool = False


class ProcessIssueRequest(BaseModel):
    issues: List[IssueData]


class Deadline(BaseModel):
    date: str
    isExceeded: bool


class ChecklistItem(BaseModel):
    id: str
    text: str
    checked: bool
    deadline: Optional[Deadline] = None

    # Using a root_validator to provide a default value for 'deadline' if it's missing
    @root_validator(pre=True)
    def set_default_deadline(cls, values):
        if 'deadline' not in values:
            values['deadline'] = None
        return values


def create_issue_model():
    dynamic_model = create_model(
        'DynamicChecklistResponse',
        **{
            TRACKER_LINK_KEY: (Optional[str], None),
            TRACKER_BREADCRUMBS_ERROR_KEY: (Optional[str], None),
            'key': (Optional[str], None),
            'checklistItems': (List['ChecklistItem'], [])
        },
        __base__=BaseModel
    )
    return dynamic_model


IssueModel = create_issue_model()
