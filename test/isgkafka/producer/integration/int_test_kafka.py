#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
A integration test program for KProducer
"""
import os
import sys
import logging
import json

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
)
from drpbase import constant
from drpbase import framework


def test_main():
    """
    A test function that uses isgkafka KProducer.
    """

    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)
    logger = logging.getLogger(constant.LOGGER_NAME)

    try:
        kproducer1 = constant.PRODUCERS.get_by_name("producer1")
        kproducer2 = constant.PRODUCERS.get_by_name("producer2")
        kproducer3 = constant.PRODUCERS.get_by_name("producer3")

        start = 110
        for idx in range(start, start + 3):
            message1 = f"This is a test message {idx} for producer1"
            # KProducer send function will return uuid after message is sent.
            # None will be returned if send function has an exception.
            uuid = kproducer1.send({"message": message1})
            logger.info("uuid for message: [%s] is %s", message1, uuid)

            message2 = f"This is a test message {idx} for producer2"
            kproducer2.send({"message": message2})
            kproducer2.send(json.dumps({"message_json": message2}))

            # If a topic doesn't exist on server, an exception will be thrown
            # A list of additional topics can be passed to send()
            # Topic format: {'name': topic_name} or {'name': topic_name, 'partition': partition_num}
            message3 = f"This is a test message {idx} for producer3"
            kproducer3.send(
                {"message": message3}, [{"name": "testTopic3"}, {"name": "testTopic5"}]
            )
            kproducer3.send(
                {"message": message3}, [{"name": "testTopic6", "partition": 1}]
            )
            kproducer3.send(
                {"message": message3}, [{"name": "testTopic4"}], msg_key="foo2"
            )

        kproducer1.close()
        constant.PRODUCERS.close_producers()
    except Exception as ex:
        logger.error(ex)


if __name__ == "__main__":
    test_main()
