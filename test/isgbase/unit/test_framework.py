#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import logging
from unittest.mock import patch

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from drpbase import constant
from drpbase import logger
from drpbase import framework


def test_setup_logger(caplog):
    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    mylogger = logging.getLogger(constant.LOGGER_NAME)
    message2 = {"message2": "2nd message"}

    mylogger.info("this is test for logger", extra=message2)

    for record in caplog.records:
        assert record.levelname == "INFO"
        assert record.asctime != ""
        assert record.pathname != ""
        assert record.lineno != ""


def test_logfilter(caplog):
    mylogger = logging.getLogger(constant.LOGGER_NAME)
    mylogger.addFilter(logger.Bind({"PR": "my_pr_number"}))

    mylogger.info("this is test for adding PR in log")
    for record in caplog.records:
        assert record.PR == "my_pr_number"

    caplog.clear()
    mylogger.addFilter(logger.Unbind(["PR"]))
    mylogger.info("this is test for removing PR in log")
    for record in caplog.records:
        assert hasattr(record, "PR") is False


def test_shutdown():
    with patch("sys.exit") as sys_exit:
        constant.FRAMEWORK.shutdown()
        sys_exit.assert_not_called()
