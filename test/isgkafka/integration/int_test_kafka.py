#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import time
import logging

from drpbase import constant
from drpbase import framework
from drpbase.utils import Utils
from drpbase.helper import Helper
from messages import mymessagefilter
from messages import mymessagehandler3
from messages import amicroservice


def cleanup(x, y):
    print(x, y)


def test_main():
    """
    A test function that uses isgkafka consumers.
    """

    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)

    # Register a signal handler function if needed
    constant.FRAMEWORK.register_pre_stop(cleanup, "desktop", "computer")
    logger = logging.getLogger(constant.LOGGER_NAME)

    last_messages = Helper.get_last_kafka_messages(
        constant.CONFIGURATION["last_message_retriever"]
    )
    logger.info("last messages: %s", last_messages)

    # Since there aren't filter and handlers defined in configuration file for consumer with name = consumer3,
    # you need to create filter and handlers and register them in that consumer. Otherwise consumer wont' start.
    message_filter = mymessagefilter.MessageFilter()
    message_handlers = []

    handler1 = mymessagehandler3.MessageHandler5(
        amicroservice.AService("drp_service", "k8s")
    )
    message_handlers.append(handler1)
    message_handlers.append(
        mymessagehandler3.MessageHandler5(
            amicroservice.AService("2nd_drp_service", "2nd_k8s")
        )
    )

    constant.CONSUMERS.register_filter("consumer3", message_filter)
    constant.CONSUMERS.register_handlers("consumer3", message_handlers)

    # An exception will be raised if the same handler is registered again
    # Uncommenting the following statement will crash this program
    # constant.CONSUMERS.register_handlers('consumer1', [handler1])

    # Get individual consumer by name if really needed. Not recommended.
    # consumer = constant.CONSUMERS.get_by_name('consumer1')

    # Change client_id/group_id
    constant.CONSUMERS.append_to_client_id("consumer1", "1234567890")
    constant.CONSUMERS.append_to_group_id("consumer1", "1234567890")

    # start individual consumer or start all consumers
    # constant.CONSUMERS.start_consumer('consumer1')
    constant.CONSUMERS.start_consumers()

    Utils.wait_for(30)

    # Stop individual consumer by name if needed
    # constant.CONSUMERS.stop_consumer('consumer1')

    while not constant.INTERRUPTED:
        logger.info("Running business logic")
        Utils.wait_for(24 * 60 * 60)

    # Stop all consumers if needed
    constant.CONSUMERS.stop_consumers()


if __name__ == "__main__":
    test_main()
