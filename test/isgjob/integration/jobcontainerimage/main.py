#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import string
import time
import logging
import argparse
from unittest.result import failfast

from drpbase import constant
from drpbase import framework


def test_main():
    """
    A test function that creates k8s jobs.
    """

    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    logger = logging.getLogger(constant.LOGGER_NAME)

    parser = argparse.ArgumentParser()
    parser.add_argument("exit_status", type=int)
    parser.add_argument("para", type=int)
    args = parser.parse_args()

    logger.info("Sleeping for 10 secs")
    time.sleep(10)
    logger.info(
        "x=%d,y=%d",
        constant.CONFIGURATION["job_container"]["x"],
        constant.CONFIGURATION["job_container"]["y"],
    )
    if isinstance(args.exit_status, int) and isinstance(args.para, int):
        logger.info("arg1=%s,arg2=%s", args.exit_status, args.para)

    if args.exit_status == 0:
        logger.info("Exit status is zero. Exiting successfully")
        exit(0)
    else:
        logger.info("Exit status is non-zero. Exiting with error")
        exit(1)


if __name__ == "__main__":
    test_main()
