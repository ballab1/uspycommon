#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)
from drpbase.configurationmanager import ConfigurationManager
from drpbase import logger
from drpbase import framework
from drpbase import constant

LOG_FILE = ""
LOGGER_NAME = "test_configuration"


def setup_module():
    global LOG_FILE
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    LOG_FILE = os.path.abspath(os.path.join(top, "test_configuration.log"))
    os.chdir(os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def run_around_tests():
    logger.setup_logger(LOGGER_NAME, "DEBUG", LOG_FILE, 1000000, 3)
    yield
    if os.path.isfile(LOG_FILE):
        os.remove(LOG_FILE)
    return


def teardown_module():
    if os.path.isfile(LOG_FILE):
        os.remove(LOG_FILE)
    return


def test_getitem():
    """Test to get the value of dictionary with bracket notation and get function"""

    config = ConfigurationManager("config/dir1/configroot.yml", LOGGER_NAME)
    assert config["logger"]["version"] == 1
    assert config.get("logger.handlers.console.formatter") == "pr_serv_formatter"

    config.add_config("config/dir1/1.build_monitor.yml")
    assert config["build_monitor"]["scrape_port"] == 8002
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]

    config.add_config("config/dir1/1.debugger.handlers.console.level.yml")
    assert config.get("debugger.handlers.console.level") == "INFO"


def test_framework_call():
    """Test to use ConfigurationManager from framework"""

    framework.UsFramework().create("config/dir1/configroot.yml", LOGGER_NAME)
    config = constant.CONFIGURATION
    assert config["logger"]["version"] == 1
    assert config.get("logger.handlers.console.formatter") == "pr_serv_formatter"

    config.add_config("config/dir1/1.build_monitor.yml")
    assert config["build_monitor"]["scrape_port"] == 8002
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]


def test_getitem_mix():
    """Test to process input argument of mix input (directory and files)"""

    # A directory and file
    config = ConfigurationManager(
        "config/dir1/,config/dir2/configroot.yml", LOGGER_NAME
    )
    assert config.get("slack.config.token") == "XOXOXOXO"

    # Directories
    config = ConfigurationManager("config/dir4/,config/dir5/", LOGGER_NAME)
    assert config["kafka"]["consumer"]["dead_letter_queue_topic"] == "techops-dlq"
    assert config["kafka"]["consumer"]["debug"]["file"] == "test.log"

    # Files
    config = ConfigurationManager(
        "config/dir4/configroot.yml,config/dir4/1.kafka.consumer.debug.yml,config/dir5/1.kafka.consumer.yml,config/dir5/2.kafka.consumer.debug.yml",
        LOGGER_NAME,
    )
    assert config.get("kafka.consumer.dead_letter_queue_topic") == "techops-dlq"
    assert config.get("kafka.consumer.debug.file") == "test.log"


def test_getitem_json():
    """Test to process input argument of json file"""

    config = ConfigurationManager("config/json_dir1/configroot.json", LOGGER_NAME)
    assert config["logger"]["version"] == 1
    assert config.get("logger.handlers.console.formatter") == "pr_serv_formatter"

    config.add_config("config/json_dir1/1.build_monitor.json")
    assert config["build_monitor"]["scrape_port"] == 8002
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]

    config.add_config("config/json_dir1/1.debugger.handlers.console.level.json")
    assert config.get("debugger.handlers.console.level") == "INFO"

    config = ConfigurationManager(
        "config/json_dir1/configroot.json,config/dir1/1.build_monitor.yml,config/dir5",
        LOGGER_NAME,
    )
    assert config["build_monitor"]["scrape_port"] == 8002
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]
    assert config.get("kafka.consumer.dead_letter_queue_topic") == "techops-dlq"
    assert config["kafka"]["consumer"]["debug"]["file"] == "test.log"


def test_getitem_error():
    """Test to validate the content of configuration file"""

    with pytest.raises(ValueError, match="Invalid configuration file"):
        ConfigurationManager(
            "config/dir3/configroot.yml,config/dir1/1.build_monitor.yml", LOGGER_NAME
        )


def test_check_overlap(caplog):
    """Test the logging of overlapping keys"""

    ConfigurationManager("config/dir4", LOGGER_NAME)
    assert "Overlapped key found" in caplog.text


def test_keyerror():
    """Test to validate keys of the dictionary"""

    config = ConfigurationManager("config/json_dir1/configroot.json", LOGGER_NAME)
    with pytest.raises(KeyError, match="'key1'"):
        print(config["key1"]["key2"]["key3"])

    with pytest.raises(KeyError, match="'key2'"):
        print(config["logger"]["key2"]["key3"])

    with pytest.raises(KeyError, match="'versio'"):
        assert config["logger"]["versio"] is None

    # get() will return None for non-existence key(s)
    assert config.get("key1.key2.key3") is None
    assert config.get("logger.key2.key3") is None

    # get() will return default value specified for non-existence key(s)
    assert config.get("logger.key2.key3", "DefaultValue") == "DefaultValue"


def test_getitem_nested():
    """Test to validate collecting config files recursively in dictionary"""

    config = ConfigurationManager("config/nested", LOGGER_NAME)
    assert config.get("debugger.handlers.console.formatter") == "pr_serv_formatter"
    assert config.get("debugger.handlers.console.level") == "INFO"
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]


def test_getitem_mixfiles():
    """Test to validate mixing input argument of yaml and json files"""

    # A directory with json and yml files
    config = ConfigurationManager("config/mix_dir", LOGGER_NAME)
    assert config.get("debugger.handlers.console.formatter") == "pr_serv_formatter"
    assert config.get("debugger.handlers.console.level") == "INFO"
    assert config.get("build_monitor.label.names") == [
        "repo_name",
        "branch_name",
        "build_type",
        "build_status",
    ]


def test_print(capfd):
    """Test __str__ function of ConfigurationManager"""

    config = ConfigurationManager("config/json_dir1/configroot.json", LOGGER_NAME)
    print(config)
    out, err = capfd.readouterr()
    assert "'class': 'logging.StreamHandler'" in out


def test_overwrite(caplog):
    """Test overwritting value based on file naming"""

    config = ConfigurationManager("config/new_dir", LOGGER_NAME)
    assert (
        config.get("logger.handlers.file.filename")
        == "/var/log/new_generic_monitor.log"
    )
    assert "Key: logger.handlers.file" in caplog.text


def test_filename():
    """Test to validate the name of configuration file"""

    # Only accept configroot if it doesn't start with digit
    with pytest.raises(
        ValueError,
        match="Invalid configuration file \\(config\\/new_dir\\/random.yml\\): Filename other than 'configroot' not allowed.",
    ):
        ConfigurationManager("config/new_dir/random.yml", LOGGER_NAME)

    # Only accept configroot if it doesn't start with digit
    with pytest.raises(
        ValueError,
        match="Invalid configuration file \\(config\\/new_dir\\/dir2\\/dir3\\/configroot.random.yml\\): Filename other than 'configroot' not allowed.",
    ):
        ConfigurationManager(
            "config/new_dir/dir2/dir3/configroot.random.yml", LOGGER_NAME
        )

    # configroot cannot be used in the middle of file name
    with pytest.raises(
        ValueError,
        match="Invalid configuration file \\(config\\/new_dir\\/dir2\\/dir3\\/1.kafka.configroot.logger.yml\\): 'configroot' cannot be in the filename.",
    ):
        ConfigurationManager(
            "config/new_dir/dir2/dir3/1.kafka.configroot.logger.yml", LOGGER_NAME
        )

    # Raise exception for non-existence file
    with pytest.raises(
        FileNotFoundError, match="No such file or directory: 'config\\/1.kafka2.yml'"
    ):
        ConfigurationManager("config/1.kafka2.yml", LOGGER_NAME)


def test_sort_filename():
    """Test to validate sorting natural number order in file name"""

    config = ConfigurationManager("config/sort/", LOGGER_NAME)
    assert config.get("kafka.consumer.client_id") == "client_id11"
    assert config["logger"]["handlers"]["mail"]["level"] == "CRITICAL-21"
