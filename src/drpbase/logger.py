################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger


old_factory = logging.getLogRecordFactory()


class RecordFactory:
    def __init__(self, base_extra):
        self.base_extra = base_extra

    # Use LogRecordFactory to add additional fields to LogRecord
    def record_factory(self, *args, **kwargs):
        record = old_factory(*args, **kwargs)

        for k in self.base_extra:
            record.__setattr__(k, self.base_extra[k])
        return record


def setup_logger(
    name, log_level, logfilepath=None, max_size=None, log_count=None, base_extra={}
):
    """1. Always log to the stdout.
    2. If logfilepath is specified, additionally log to a file and in this case
       it's an error not to specify max size and max num of log files to be kept.
    3. Logs are in json.
    """
    rf = RecordFactory(base_extra)
    logging.setLogRecordFactory(rf.record_factory)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    user_format = "".join(["%({0})s".format(k) for k in base_extra.keys()])
    formatter = jsonlogger.JsonFormatter(
        "{0}%(asctime)s%(message)s%(levelname)s%(pathname)s%(lineno)d".format(
            user_format
        )
    )

    s_handler = logging.StreamHandler()
    s_handler.setFormatter(formatter)
    logger.addHandler(s_handler)

    if logfilepath is not None:
        if max_size is None or log_count is None:
            raise ValueError(
                "log file max size and how many file to keep need to be specified."
            )
        f_handler = RotatingFileHandler(
            logfilepath, maxBytes=max_size, backupCount=log_count
        )
        f_handler.setFormatter(formatter)
        logger.addHandler(f_handler)

    logger.info("Logger of name=%s initialized", name)
    return logger


class Bind(logging.Filter):
    """
    A logging filter class that allows extra custom attributes to be added in log
    """

    def __init__(self, attributes: dict):
        """
            The user calls the constructor supplying a dictionary of (key, value) pairs
            to be added to the subsequent log messages.
        Args:
            attributes (dict): (key, value) pairs to be added to the log message
        """
        super().__init__()
        self.attributes = attributes

    def filter(self, record):
        """
            Called by python. internal function.
        Args:
            record (LogRecord): a log record
        Returns:
            bool: True
        """
        for k in self.attributes:
            setattr(record, k, self.attributes[k])

        return True


class Unbind(logging.Filter):
    """
    A logging filter class that removes custom attributes if they exist in log
    """

    def __init__(self, attribute_names: list[str]):
        """
            The user calls the constructor supplying a list of keys to be deleted
            from the subsequent log messages.
        Args:
            attribute_names (list[str]): List of keys to be deleted in log messages
        """
        super().__init__()
        self.attribute_names = attribute_names

    def filter(self, record):
        """
            Called by python. internal function.
        Args:
            record (LogRecord): a log record
        Returns:
            bool: True
        """
        for name in self.attribute_names:
            if hasattr(record, name):
                delattr(record, name)

        return True
