################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import logging
from drpbase import constant
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler2(AbcMessageHandler):
    def __init__(self):
        self.logger = logging.getLogger(constant.LOGGER_NAME)

    def handle_messages(self, message):
        if message.topic() == "testTopic5":
            self.logger.info(
                f"handler2: Topic: {message.topic()} Partition: {message.partition()} "
                + f"Offset: {message.offset()} Message: {message.value()}"
            )
