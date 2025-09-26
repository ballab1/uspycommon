################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import json
import re
import collections.abc as collections_abc
from collections import defaultdict
import logging
import itertools
import yaml
from . import constant


class ConfigurationManager:
    """1. If the input is a single directory, the ConfigurationManager identifies and consolidates all
        configuration files (json/yml) located under the specified directory and returns
        a single configuration dictionary. All other files are ignored.
     2. If the input is multiple directories, it will do the same as above.
     3. If the input is multiple files, it will consolidate the file contents to produce a single dictionary.
     4. User can also mix and match directories and files in the input.

     Each json/yml file must start with a number, followed by a series of dot-separated string values.

     Each dot separation indicates nesting in the dictionary. For example,
     if the filename is 10.level1.level2.yml and the content in the file is "key: value", the dictionary will
     look like below (the number in the front is stripped)
       level1:
         level2:
           key: value
     And the key value can be accessed as ['level1']['level2']['key'].
     The only exception to the above rule is the filename "configroot.yml". This filename is used to place the
     content at the root level of the dictionary (i.e., which can be accessed as ['key']). For example, if the
     filename is `configroot.yml` and the file content is `key: value`, the dictionary will look like below
       key: value
     Not allowed - 1. the value `configroot` at any other level, e.g., level1.configroot.yml. 2. the value
    `configroot`, followed by another level, e.g., configroot.level1.yml. 3. a number in front of the filename
     `configroot.yml', e.g. `1.configroot.yml`. Violation will throw ValueError exception.

     The number in front of the filename (e.g., <NUMBER>.level1.level2.yml) indicates how to determine
     the final value in the case of overlapped keys. For example, if the content of 1.level1.level2.yml
     and 2.level1.level2.yml is the same for a key at the same level, the value from 2.level1.level2.yml
     will be used. Each filename must start with a number. If it does not, ValueError exception will be thrown.
    """

    extension_loader_map = {
        ".yml": yaml.safe_load,
        ".yaml": yaml.safe_load,
        ".json": json.loads,
    }

    def __getitem__(self, key):
        return self._config[key]

    def __str__(self):
        return str(self._config)

    def __init__(self, conf_dir, logger_name=constant.LOGGER_NAME):
        """conf_dir supports
        1. string input of file names (e.g. ConfigurationManager("l1.yml,l1.l2.yml,l3.yml,
             root.yml")
        2. string input of directory names (e.g. ConfigurationManager("/dir1,/dir2"). In this case,
           all json and yaml files, located under both dir1 and dir2 will be merged to produce
           a single dictionary.
        3. string input of both file and directories (e.g. ConfigurationManager("/dir1,l1.l2.yml")
        """
        self.logger = logging.getLogger(logger_name)
        self._config = defaultdict(dict)
        self._load_files(conf_dir)

    def _load_files(self, config):
        """Load files from string or directory argument"""

        unsorted_items = []
        for input_item in config.split(","):
            if os.path.isdir(input_item):
                # Get list of files with their full path in directory
                for folder, _, files in os.walk(input_item):
                    for file_item in files:
                        filepath = os.path.abspath(os.path.join(folder, file_item))
                        unsorted_items.append(filepath)
            else:
                unsorted_items.append(input_item)

        # Check for valid file name
        for item in unsorted_items:
            file_name = os.path.basename(item)
            if not file_name[:1].isdigit():
                filestr, ext = os.path.splitext(file_name)
                if filestr != constant.ROOT_FILE:
                    self.logger.error(
                        "Invalid configuration file (%s): Filename other than '%s' not allowed.",
                        item,
                        constant.ROOT_FILE,
                    )
                    raise ValueError(
                        "Invalid configuration file ({}): Filename other than '{}' not allowed.".format(
                            item, constant.ROOT_FILE
                        )
                    )
            else:
                if constant.ROOT_FILE in file_name:
                    self.logger.error(
                        "Invalid configuration file (%s): '%s' cannot be in the filename.",
                        item,
                        constant.ROOT_FILE,
                    )
                    raise ValueError(
                        "Invalid configuration file ({}): '{}' cannot be in the filename.".format(
                            item, constant.ROOT_FILE
                        )
                    )

        # Make sure the "digit" file(s) at the beginning of the list
        presorted_items = sorted(unsorted_items, key=lambda t: os.path.basename(t))
        # Reorder configuration files in ascending order per natural number magnitude.
        #   Put root/non-digit file in the front of the list.
        tmp_list = [
            list(y)
            for x, y in itertools.groupby(
                presorted_items, lambda f: os.path.basename(f)[0].isdigit()
            )
        ]
        items_to_load = sorted(tmp_list[-1], key=lambda y: os.path.basename(y))
        root_idx = [
            i
            for i, item in enumerate(items_to_load)
            if re.search(constant.ROOT_FILE, item)
        ]
        # Make sure ROOT_FILE is the first one on the list
        r_idx = 0
        for idx in root_idx:
            items_to_load.insert(r_idx, items_to_load.pop(idx))
            r_idx += 1

        if len(tmp_list) > 1:
            digit_list = sorted(
                tmp_list[0],
                key=lambda z: (
                    int(os.path.basename(z).partition(".")[0]),
                    z.split(".", 1)[1],
                ),
            )
            # Combine the two lists for processing
            items_to_load.extend(digit_list)

        extensions = ConfigurationManager.extension_loader_map.keys()
        # Iterate through files in the list
        for item in items_to_load:
            if re.match(
                r"(.*)([\w-]+.*)({})\s*(#.+)?$".format("|".join(extensions)), item, re.I
            ):
                file_item = os.path.basename(item)
                filename, ext = os.path.splitext(file_item)
                loader = ConfigurationManager.extension_loader_map[ext]
                if filename[:1].isdigit():
                    filename = filename.split(".", 1)[1]
                self._load(item, loader, key=filename)

    def _load(self, config_file, loader, key):
        """Load individual file from argument"""

        try:
            with open(config_file, "r") as file_strm:
                value = loader("".join(file_strm.read()).strip())
        except FileNotFoundError as file_err:
            self.logger.error(
                "File not found. Exception type: %s, Message: %s",
                file_err.__class__.__name__,
                str(file_err),
            )
            raise file_err

        # Get the new config dictionary
        keys = key.split(".")
        new_config = new_obj = {}
        for key_item in keys[:-1]:
            new_obj = new_obj.setdefault(key_item, {})
        new_obj[keys[-1]] = value

        if keys[0] == constant.ROOT_FILE:
            new_config = new_config[constant.ROOT_FILE]

        # Check for valid content
        if isinstance(new_config, dict):
            # Check for overlapped keys for debugging
            int_flag, int_list_str = self._check_entries(new_config)
            if not int_flag:
                self.logger.debug(
                    "Overlapped key found. File: %s Key: %s", config_file, int_list_str
                )
            self._config = dict(self._merge_entries(self._config, new_config))
        else:
            self.logger.error("Invalid configuration file (%s)", config_file)
            raise ValueError("Invalid configuration file ({})".format(config_file))

    def _merge_entries(self, old_entry, new_entry):
        """Merge both dictionaries (new_entry will overwrite old_entry)"""

        for key in set(old_entry.keys()).union(new_entry.keys()):
            if key in old_entry and key in new_entry:
                if isinstance(old_entry[key], dict) and isinstance(
                    new_entry[key], dict
                ):
                    yield (
                        key,
                        dict(self._merge_entries(old_entry[key], new_entry[key])),
                    )
                else:
                    yield (key, new_entry[key])
            elif key in old_entry:
                yield (key, old_entry[key])
            else:
                yield (key, new_entry[key])

    def _check_entries(self, dct):
        """Check for overlapped keys"""

        new_lst = []
        for new_items in self._get_key_list(dct):
            new_lst.append(new_items[:-1])
        old_lst = []
        for old_items in self._get_key_list(self._config):
            old_lst.append(old_items[:-1])

        if not old_lst:
            return True, []

        int_list = list(set(new_lst).intersection(set(old_lst)))
        if int_list:
            # Return the overlapping keys for debugging
            return False, ".".join(int_list[0])

        return True, []

    def _get_key_list(self, dct):
        """Get a list of all possible keys order from a dictionary"""

        # Iterate over all key-value pairs of dict argument
        for key, value in dct.items():
            # Check if value is of dict type
            if isinstance(value, dict):
                # If value is dict then iterate over all its values
                for pair in self._get_key_list(value):
                    yield (key, *pair)
            else:
                # If value is not dict type then yield the empty value since we don't care about the value.
                yield (key, "")

    def get(self, keys, defvalue=None):
        """Key can be in dot notation (e.g. .get("l1.l2.key")).
        If not found, default value will be returned.
        """
        current_data = self._config

        for key in keys.split("."):
            if isinstance(current_data, collections_abc.Mapping):
                current_data = current_data.get(key, defvalue)

        return current_data

    def add_config(self, config):
        """Add configuration to dictionary"""

        self._load_files(config)
