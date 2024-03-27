from enum import Enum
from typing import TypeVar, Generic, Type, Optional

import structlog
from fastapi import HTTPException


class LastLogSafeCaptureProcessor:
    def __init__(self):
        self.last_log = None

    def __call__(self, _, __, event_dict):
        if event_dict['level'] == 'error':
            self.last_log = {
                k: v for k, v in event_dict.items()
                if k != 'exception'
            }
        else:
            self.last_log = event_dict
        return event_dict


last_log_safe_capture_processor = LastLogSafeCaptureProcessor()

T = TypeVar('T', bound=Exception)


class LoggerUtils(Generic[T]):
    class levels(Enum):
        WARNING = 'warning'
        ERROR = 'error'
        INFO = 'info'
        DEBUG = 'debug'

    def __init__(self, module_name):
        self._logger = structlog.get_logger(module_name)
        self.last_log_safe_capture_processor = last_log_safe_capture_processor

    def _get_log_cbk(self, level: 'LoggerUtils.levels'):
        return getattr(self._logger, level.value)

    def log(self, msg_or_err_code, level: 'LoggerUtils.levels',
            e: Optional[Exception] = None, **logging_kwargs):
        if e:
            error_context = getattr(e, 'error_context', {})
            if error_context:
                logging_kwargs = {**error_context, **logging_kwargs}
            logging_kwargs['exc_info'] = True
            logging_kwargs['exception_type'] = type(e).__name__
            logging_kwargs['exception_msg'] = str(e)

            original_exceptions = getattr(e, 'original_exceptions', [])
            # Handle original exceptions stack
            if original_exceptions:
                orig_excp_info = self._format_original_exceptions(
                    original_exceptions)
                logging_kwargs['original_exceptions'] = orig_excp_info
        self._get_log_cbk(level)(msg_or_err_code, **logging_kwargs)
        return self.last_log_safe_capture_processor.last_log

    def _format_original_exceptions(self, exceptions):
        """Formats the original exceptions stack into a string."""
        return ' | '.join([
                              f"{type(ex).__name__}: {ex} (Context: {getattr(ex, 'error_context', {})})"
                              for ex in exceptions])

    def create_exception(self, err_code: str, err_type: Type[T],
                         err_kwargs: Optional[dict] = None, log: bool = True,
                         original_exception: Optional[Exception] = None,
                         **error_context_kwargs) -> T:
        err_kwargs = err_kwargs or {}
        if issubclass(err_type, HTTPException):
            # Special handling for DRF exceptions
            traceback_detail = {}
            if original_exception:
                traceback_detail['traceback'] = self.log(err_code,
                                                         self.levels.ERROR,
                                                         e=original_exception)
            detail = dict(error=err_code, data=error_context_kwargs,
                          **traceback_detail)
            err = err_type(detail=detail, **err_kwargs)
            # err = err_type(detail=err_code, **dict(data=data, **err_kwargs))
        else:
            # Normal handling for standard exceptions
            err = err_type(err_code, **err_kwargs)

        # Attach error context as an attribute
        err.error_context = error_context_kwargs

        # Store the original exception, if provided
        if original_exception:
            err.original_exceptions = getattr(original_exception,
                                              'original_exceptions', [])
            err.original_exceptions.append(original_exception)

        # Logging if needed
        if log:
            self.log(err_code, level=self.levels.ERROR, e=err)

        return err


if __name__ == '__main__':
    logger = structlog.get_logger(__name__)
    logger.info("test_log_message", browser="Chrome", port=9222)
