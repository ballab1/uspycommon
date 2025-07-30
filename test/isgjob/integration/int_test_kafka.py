#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import logging
from drpbase import constant
from drpbase import framework
from drpbase.utils import Utils


def handle_job_result(job):
    print(f"k8s_job: {job.metadata.name} call back function executes...")


def test_main():
    """
    A test function that uses isgkafka consumers and job manager.
    """

    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    logger = logging.getLogger(constant.LOGGER_NAME)

    constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = handle_job_result
    constant.CONSUMERS.start_consumers()

    while not constant.INTERRUPTED:
        logger.info("Running business logic")
        Utils.wait_for(24 * 60 * 60)

    constant.CONSUMERS.stop_consumers()


if __name__ == "__main__":
    test_main()
