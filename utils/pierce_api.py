import json
import re
from collections import defaultdict
from typing import Union, Tuple, Any

from config.config import get_settings
from models import IssueData
from utils.log import LoggerUtils
from utils.utils import ErrorList


def get_api_url_for_small_resource(resource, resource_id):
    """Generate API URL for small resources (tasks, lessons)."""
    return f'https://prestable.pierce-admin.praktikum.yandex-team.ru/content/{resource}s/{resource_id}/breadcrumbs/'


def get_resource_plural_name(resource: str) -> str:
    return 'faculties' if resource == 'faculty' else f'{resource}s'


def get_api_url_for_big_resource(resource, resource_id):
    """Generate API URL for big resources (topics, courses, etc.)."""
    resource_plural = get_resource_plural_name(resource)
    return f'https://prestable.pierce-admin.praktikum.yandex-team.ru/content/{resource_plural}/{resource_id}/'


def identify_resource(url: str) -> tuple:
    """
    Identify the resource type a URL is pointing at.
    Returns a tuple of the singular and plural names of the resource, its API URL, and the resource ID.
    """
    url = url.split('?')[0]

    for resource in small_resource_types:
        match = re.search(fr'/{resource}s?/([^/]+)', url, re.IGNORECASE)
        if match:
            resource_id = match.group(1)
            api_url = get_api_url_for_small_resource(resource, resource_id)
            return (resource, f'{resource}s', api_url, resource_id)

    for resource in big_resource_types:
        resource_plural = get_resource_plural_name(resource)
        match = re.search(fr'/(?:{resource}|{resource_plural})/([^/]+)', url, re.IGNORECASE)
        if match:
            resource_id = match.group(1)
            api_url = get_api_url_for_big_resource(resource, resource_id)
            return (resource, resource_plural, api_url, resource_id)

    raise ValueError('Invalid URL or unsupported resource type')


def build_resource_url(resource_plural: str, resource_id: str):
    return f'https://prestable.pierce-admin.praktikum.yandex-team.ru/content/{resource_plural}/{resource_id}/'


def preprocess_url(url: str) -> str:
    """
    Simplify URL to remove parameters and identify the API URL.
    """
    # Remove URL parameters
    url = url.split('?')[0]

    # Identify resource type and get API URL
    try:
        _, _, api_url, _ = identify_resource(url)
        return api_url
    except ValueError as e:
        raise LoggerUtils(__name__).create_exception('url_preprocessing_error', ValueError, log=True,
                                                     original_exception=e, url=url)


async def postprocess_fetched_data(
        browser_manager, url, data: Union[dict, list], issue: IssueData,
        checklist_error_messages: ErrorList[Tuple[str, str]]) -> dict:
    settings = await get_settings()
    all_resource_types = big_resource_types + small_resource_types
    result = defaultdict(lambda: defaultdict(str))
    if isinstance(data, list):
        # data coming from the resource/breadcrumbs endpoint
        for level in data:
            if level['type'] in all_resource_types:
                result[level['type']]['id'] = level['id']
                result[level['type']]['name'] = level['name']
    elif isinstance(data, dict):
        # data coming from the resource/<resource_id> endpoint
        for level in all_resource_types:
            if f'{level}_id' in data:
                result[level]['id'] = data[f'{level}_id']
    end_resource, end_resource_plural, api_url, end_resource_id = identify_resource(url)
    if end_resource not in result:
        result[end_resource]['id'] = end_resource_id
    sprint_id = extract_sprint_id(issue.link)
    if sprint_id:
        result['sprint']['id'] = sprint_id

    def get_resource_info_key(_resource_info, _key, _key_with_resource):
        result = resource_info.get(_key, None)
        errors = resource_info.get('errors', [])
        if errors and not settings['ignore_errors'].get(_key_with_resource):
            raise LoggerUtils(__name__).create_exception(
                'RESOURCE_INFO_KEY_ERROR', KeyError, upstream_error=str(errors), key=_key, key_with_resource=_key_with_resource)
        return result

    for resource in result:
        resource_data = result[resource]
        if ('name' not in resource_data and resource != 'task') or (
                resource == 'task' and 'description' not in resource_data):
            resource_plural = get_resource_plural_name(resource)
            resource_url = build_resource_url(resource_plural, resource_data['id'])
            resource_info = {}
            try:
                resource_info = await browser_manager.fetch_from_external_api_async(
                    resource_url, 'postprocess_fetched_data')
                if 'position' in resource_info:
                    result[resource]['position_if_exists'] = get_resource_info_key(
                        resource_info, 'position', f'{resource}.position')
                if resource == 'task':
                    result[resource]['description'] = get_resource_info_key(
                        resource_info, 'description', f'{resource}.description')
                    result[resource]['position'] = get_resource_info_key(
                        resource_info, 'position', f'{resource}.position')
                else:
                    result[resource]['name'] = get_resource_info_key(
                        resource_info, 'name', f'{resource}.name')
            except Exception as e:
                error_msg = LoggerUtils(__name__).log(
                    'postprocess_fetched_data_error', LoggerUtils.levels.ERROR, e=e,
                    resource_info=json.dumps(resource_info), url=url, issue=issue.model_dump_json())
                await checklist_error_messages.append((issue.key, error_msg))
                continue
    return result


def extract_sprint_id(url):
    # Define a regular expression pattern to match the sprint ID
    pattern = r'/sprints/(\d+)/'

    # Use re.search to find the match in the URL
    match = re.search(pattern, url)

    if match:
        # Group 1 of the match contains the sprint ID
        sprint_id = match.group(1)
        return sprint_id
    else:
        # If no match is found, return None or raise an exception as needed
        return None


big_resource_types = ['topic', 'sprint', 'course', 'track', 'profession', 'faculty']
small_resource_types = ['task', 'lesson']
