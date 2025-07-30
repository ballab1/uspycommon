#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import logging

from drpbase import constant
from drpbase import framework


def test_main():
    """
    A test function that uses isgkafka consumers.
    """

    configdir = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "configkafkaproducer")
    )
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    logger = logging.getLogger(constant.LOGGER_NAME)
    logger.info("Kafka consumer running")
    constant.CONSUMERS.start_consumers()


if __name__ == "__main__":
    test_main()
