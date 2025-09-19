#!/usr/bin/env python3
################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import logging
from drpbase import framework, constant


def test_main():
    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    lgr = logging.getLogger(constant.LOGGER_NAME)
    # Register metrics. Monitoring has already been started by the framework
    lgr.info("Will register application metrics")
    constant.MONITOR.register_metrics(constant.CONFIGURATION["monitor"]["metrics"])
    # Don't exit the main thread.
    constant.FRAMEWORK.wait()


if __name__ == "__main__":
    test_main()
