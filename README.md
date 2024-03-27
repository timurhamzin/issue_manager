# Breadcrumbs: Automated Issue Processing and Management

Breadcrumbs is an automated system designed to streamline issue processing and management. Utilizing FastAPI for backend services, browser automation, and sophisticated data fetching mechanisms, Breadcrumbs efficiently processes issues, updates their statuses, and manages checklists.

## Overview

The application focuses on managing and processing issues from a tracker system. It automates checklist item checking, updates issue fields based on fetched data, and optionally deletes completed checklist items. The system operates continuously, ensuring that issues are always up-to-date.

### Purpose of the App

Breadcrumbs is tailored to annotate issues with relevant information, placing them within a professional, track, course, or topic context. It uses a checklist as a task queue, where each item represents an issue to be processed. The system fetches data from various external API endpoints, providing detailed information about tasks, lessons, and other resources.

### Checklist Management and Issue Processing

The checklist serves as a task queue, with each item representing an issue to be processed. The application fetches data for individual issues, updates their fields accordingly, and manages the checklist to ensure all issues are addressed.

## Configuration and Environment Variables

Breadcrumbs is configurable through environment variables and a `settings.json` file. These settings control various aspects of the application, ensuring flexible and secure operation.

### Environment Variables:

Key environment variables include:

- `TRACKER_OAUTH_TOKEN`: Authorization token for issue tracker requests.
- `DEBUGGING_BROWSER_PORT`, `BROWSER_TYPE`, `DRIVER_SERVICE`, `BROWSER_PATH`, `REMOTE_DEBUGGING_PORT`: Control the browser automation setup.
- `DEFERRED_CHECKLIST_ITEMS_FUTURE_DATETIME`: Issue checklist items after this date will be revisited by uncheck_deferred_issues_with_clean_error_field and unchecked if their issues' field <TRACKER_BREADCRUMBS_ERROR_KEY> is cleared.

### JSON Configuration File (`settings.json`)

The `settings.json` file allows adjusting parameters that control the application's behavior:

```json
{
    "process_checklist_frequency_seconds": 30,
    "delete_done_checklist_items": false,
    "modify_browser_page_on_fetch": false
}
```

- `process_checklist_frequency_seconds`: The frequency, in seconds, at which the checklist is processed. This determines how often the application checks the checklist for new items to process.
- `delete_done_checklist_items`: A boolean indicating whether completed checklist items should be automatically deleted. If `true`, items that have been processed and are marked as done will be removed from the checklist.
- `modify_browser_page_on_fetch`: A boolean that controls the modification of the browser page when fetching data from external APIs. If `true`, the browser page will display the fetched data. This is useful for debugging or monitoring purposes. If `false`, the browser page will not display the fetched data, which is preferable in a production environment for performance reasons.

These settings provide a flexible way to adjust the application's behavior without modifying the code.

## Technical Structure

Breadcrumbs is structured as a Python application utilizing FastAPI for its web framework, enabling asynchronous task handling and providing a robust API layer.

### Main Components:

1. **FastAPI Application (`main.py`):** The core of the application, setting up the server, initializing background tasks, and handling API requests.
   
2. **API Layer (`api.py`):** Defines the logic for processing checklists and issues, including fetching data, updating tracker fields, and handling errors.
   
3. **Browser Automation (`browser_manager.py`):** Manages browser interactions, executing JavaScript, and handling file downloads for fetching data. The browser is automated to provide the desired access level to an external API that requires browser cookies.
   
4. **Issue Processing (`process_issue.py`):** Contains the logic for processing individual issues, updating tracker fields, and handling processing errors.
   
5. **Tracker Interaction (`tracker.py`):** Manages communication with the issue tracker, including fetching issues, patching data, and logging errors.

### Key Features:

- **Continuous Processing:** The application continuously processes checklists at a configurable frequency, ensuring that issues are always updated.
  
- **Error Handling and Logging:** Extensive logging and error handling ensure that any issues during processing are recorded and can be addressed.
  
- **Browser Automation:** Leverages browser automation for fetching data, making the application capable of handling complex data retrieval scenarios, including access to an external API that requires browser cookies.
  
- **Configurable Settings:** Settings for processing frequency and other behaviors can be updated on-the-fly via API endpoints (`/set_settings`, `/uncheck_deferred_issues_with_clean_error_field`, `/process_checklist_now`), allowing for dynamic configuration and immediate processing.

## Interacting with Breadcrumbs

### Starting the Application:

- Download latest Chrome Driver.
- Download Chrome version for the downloaded version of Chrome Driver (e.g. Chrome version 114.0.5735.90 for Chrome Driver version 114.0.5735.90).
- Create a .env file by copying example.env, setting variables enclosed in <> to your values.
- Review the config/settings.json file an set time limits as to your preference.
- Paths to files and directories should be absolute. On Windows use double backslashes in paths.
- If you place the Chrome Driver in the project directory, DRIVER_SERVICE can be set to the filename without the path.
- Run the application by executing the `run.py` file (issuing `python run.py` command in the terminal). 
  This will start the FastAPI server and initialize the background tasks for processing checklists.

#### Setting up Chrome
- Open Chrome and log in to https://mail.yandex-team.ru/ to update cookies. You will need to log in each time cookies expire.
- On your first run, you may want to turn off the "Ask where to save each file before downloading" Chrome setting
- Turning on "Show downloads when they're done" Chrome setting might be useful if you want to control the program operation visibility. 
  
On your first run:
- Open Chrome's settings.
- Navigate to 'Site Settings' under 'Privacy and Security'.
- Expand the 'Additional permissions' section.
- Select 'Automatic downloads'.
- You can then toggle the setting to ask when a site tries to download files automatically after the first file. This can prevent the prompt for each download.
  
### API Endpoints:

- **POST `/set_settings`**:
  - Updates the application settings.
  - Requires an API key for authentication.
  - Accepts JSON payload with the new settings.

- **POST `/uncheck_deferred_issues_with_clean_error_field`**:
  - Unchecks deferred issues without errors, facilitating re-processing and error correction.
  - Requires an API key for authentication.

- **POST `/process_checklist_now`**:
  - Triggers immediate processing of the checklist, bypassing the scheduled frequency.
  - Requires an API key for authentication.

### Usage:

1. **Update Settings**: To change the application's behavior, modify the `settings.json` file with the desired values. Changes will take effect when the application is restarted. Alternatively, update settings on the fly temporarily (until the app is restarted) by sending a POST request to `/set_settings` with the updated values and the correct API key in the headers.

2. **Monitor Logs:**
   Keep an eye on the error logs saved in the tracker on the patched issues' field given by the `TRACKER_BREADCRUMBS_ERROR_KEY` environment variable, and the same field on the issue used for the checklist storage. The issues causing errors are not checked out in the checklist, and the checklist items are kept even if the `delete_done_checklist_items` is set to `True`.


## Updates

### 2024-02-08 Updates

#### Enhancements

- Introduced Pydantic for model validation and settings management, enhancing configuration handling (`config/config.py`).
- Added a new `ConfigModel` class to dynamically load settings from `settings.json`, improving configuration flexibility (`config/config.py`).
- Updated file reading operations to specify `encoding='utf-8'`, standardizing file handling across environments (`config/config.py`).
- Implemented asynchronous functions `update_settings` and `uncheck_deferred_issues_continuously` to refine the application's background processing capabilities (`main.py`).
- Adjusted the error handling in `postprocess_fetched_data` within `utils/pierce_api.py` to include more descriptive error information, enhancing debuggability.

#### Refactoring

- Moved the definition of `ConfigModel` from `models.py` to `config/config.py`, centralizing configuration-related code.
- Simplified the import statements in `main.py` by adjusting the scope of imported functions and classes, reducing complexity.

#### Bug Fixes

- Fixed potential UnicodeDecodeError by setting the file reading encoding to 'utf-8' in configuration file loading.
- Adjusted logic in `utils/pierce_api.py` to correctly handle errors based on the updated `ignore_errors` settings structure.

#### Configuration Changes

- Added a new setting `uncheck_deferred_issues_frequency_seconds` with a default value of 3600 seconds in `settings.json`, allowing for more granular control over issue management.

#### Code Cleanup

- Enhanced consistency in error logging by including additional context in exception generation (`utils/pierce_api.py`).
