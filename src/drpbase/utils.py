################################################################################
# Copyright (c) 2022-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import time
import functools
import logging
import socket
from typing import List
from collections import defaultdict
from . import constant
import fnmatch
import re

logger = logging.getLogger(constant.LOGGER_NAME)


class Utils:
    def attempt(exceptions=Exception, attempts=None, interval=None):
        """A attempt decorator that will call function multiple times based on arguments.

        Args:
            exceptions (exception_, optional): an exception or a tuple of exceptions to catch. Defaults to Exception.
            attempts (int, optional): the maximum number of attempts (function call). Defaults to None.
                                    If None, it will use value of MAX_ATTEMPTS defined in framework.
                                    The minimum value is 1.
            interval (int, optional): delay between attempts in seconds. Defaults to None.
                                    If None, it will use value of ATTEMPT_INTERVAL defined in framework.
        """

        def attempt_decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if attempts is None:
                    _attempts = constant.MAX_ATTEMPTS
                else:
                    _attempts = attempts

                if interval is None:
                    _interval = constant.ATTEMPT_INTERVAL
                else:
                    _interval = interval

                while _attempts:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as ex:
                        _attempts -= 1
                        if not _attempts:
                            raise

                        logger.info(
                            f"Exception raised in {func.__name__} function. "
                            + f"Exception: {str(ex)}, retrying in {_interval} seconds"
                        )

                    time.sleep(_interval)

            return wrapper

        return attempt_decorator

    @classmethod
    def get_config_value(
        cls, config, key, is_required=False, is_list=False, default=None
    ):
        """
        Get the value of a key from configuration dictionary.

        Args:
            config (dict): Dictionary containing config
            key (str): key name of dictionary
            is_required (bool, optional): Is this key required in dictionary. Defaults to False.
            is_list (bool, optional): Is value of key a List_. Defaults to False.
            default (object, optional): default value to return if no found. Defaults to None.

        Raises:
            ValueError: Value of Key: {key} not found.
            ValueError: Value of Key: {key} isn't a List.
            ValueError: Value of Key: {key} cannot contain empty value in List
            ValueError: Value of Key: {key} cannot be empty

        Returns:
            object: Value of key
        """
        value = config.get(key)

        if value is None:
            if not is_required:
                return default
            else:
                logger.error(f"Value of key: {key} not found")
                raise ValueError(f"Value of key: {key} not found")

        if is_list:
            if isinstance(value, List) is False:
                logger.error(f"Value of key: {key} isn't a List")
                raise ValueError(f"Value of key: {key} isn't a List")

            if not all(value):
                logger.error(f"Value of key: {key} cannot contain empty value in List")
                raise ValueError(
                    f"Value of key: {key} cannot contain empty value in List"
                )

        if isinstance(value, str) and len(value) == 0:
            logger.error(f"Value of key: {key} cannot be empty")
            raise ValueError(f"Value of key: {key} cannot be empty")

        return value

    @staticmethod
    def wait():
        """
        wait forever. The function will exit if interrupted flag is True
        """
        while not constant.INTERRUPTED:
            time.sleep(constant.SIGNAL_HANDLER_WAIT_TIME)

    @staticmethod
    def wait_for(wait_time=constant.SLEEP_TIME):
        """
            Wait for specified number of seconds
        Args:
            wait_time (integer, optional): number of seconds. Defaults to constant.SLEEP_TIME.
        """
        already_wait = 0

        while not constant.INTERRUPTED and already_wait < wait_time:
            time.sleep(constant.SIGNAL_HANDLER_WAIT_TIME)
            already_wait += constant.SIGNAL_HANDLER_WAIT_TIME

    @staticmethod
    def check_servers(servers):
        """
            Check if servers are reachable.
        Args:
            servers (list): a list of servers with string format, address:port.

        Returns:
            dict: a dictionary with server address as key and bool as value to indicate
                if a server is reachable or not. If value is True, that means server is online.
        """
        results = {}
        for server in servers:
            address, port = server.split(":")
            try:
                with socket.create_connection((address, port), timeout=1):
                    results[address] = True
            except (socket.timeout, ConnectionRefusedError):
                results[address] = False

        return results

    @staticmethod
    def get_secret(
        key: str, mount_path: str = "/etc/secrets/", retry_attempt: int = 0
    ) -> str:
        """Returns the secret value stored against the input token. If no stored value is found,
        None is returned. If retry_attempt is set to an integer value greater than 0, the framework
        will refresh the stored secret values from the vault and return the updated value. Therefore,
        setting retry_attempt to non-zero may cause a delay. The application will set retry_attempt to a
        non-zero value, only when it finds out that the returned secret value is stale,
        i.e., the application got an authorization error using the returned value.
        Currently, all values, greater than 0 are ignored.
        """

        secret = None
        try:
            if retry_attempt > 0:
                pass  # Call restful api of secret-manager to refresh app-secret. Not implemented yet.

            if mount_path[-1] != "/":
                mount_path = mount_path + "/"

            with open(mount_path + key, "r", encoding="utf-8") as f:
                secret = f.read()
        except (IOError, FileNotFoundError) as ex:
            logger.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )

        return secret

    @staticmethod
    def get_combined_dict_of_list(dictionary1: dict, dictionary2: dict) -> dict:
        """
        Combine two dictionaries of list, values of common keys will be extended into list items

        Args:
            dictionary1 (dict) : Dictionary 1 with list as values
            dictionary2 (dict) : Dictionary 2 with list as values

        Returns:
            dict
        """
        resultant_dict = defaultdict(list)
        for dictionary in (dictionary1, dictionary2):
            for key, value in dictionary.items():
                resultant_dict[key].extend(value)

        return dict(resultant_dict)

    @staticmethod
    def exception_handler(func):
        """
        Wrapper function for exception handling
        """

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as err:
                logger.error(
                    f"Failed with error: {err} \nException type: {err.__class__.__name__}"
                )
                raise

        return wrapper

    @staticmethod
    def match_with_exclusion_patterns(filename: str, exclusion_files: list) -> bool:
        """
        Determine if filename matches any filenames in list of exclusion files

        Args:
            filename (str): Filename to match
            exclusion_files (list): List of filenames to exclude

        Returns:
            Bool
        """
        if not exclusion_files:
            return False
        for pattern in exclusion_files:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    @staticmethod
    def match_with_exclusion_folders(filename: str, exclusion_folders: list) -> bool:
        """
        Determine if filename matches any folders in list of exclusion folders

        Args:
            filename (str): Filename to match
            exclusion_folders (list): List of folders to exclude

        Returns:
            Bool
        """
        if not exclusion_folders:
            return False
        for pattern in exclusion_folders:
            mt = re.match(pattern, filename)
            if mt:
                return True
        return False
