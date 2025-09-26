################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import logging
from drpbase import constant
from drpbase import logger
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler3(AbcMessageHandler):
    def handle_messages(self, message):
        if message.topic() == "testTopic2":
            print(
                f"handler3: Topic: {message.topic()} Partition: {message.partition()} Offset: {message.offset()}"
            )


class MessageHandler4(AbcMessageHandler):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(constant.LOGGER_NAME).getChild(
            "MessageHandler4"
        )

    def handle_messages(self, message):
        if message.topic() == "testTopic3":
            self.logger.addFilter(
                logger.Bind({"T3_TOPIC": message.topic(), "PR": {"data": {2: "XX"}}})
            )

            self.logger.info(
                f"handler2: Topic: {message.topic()} Partition: {message.partition()} "
                + f"Offset: {message.offset()} Message: {message.value()}"
            )
            # Because of using child logger, the binding of T3_TOPIC and PR
            # is only applied in this class. T3_TOPIC won't be shown in another MessageHandler log.
            self.logger.info("T3_TOPIC and PR are added in log")

            self.logger.addFilter(logger.Unbind(["T3_TOPIC", "PR"]))
            self.logger.info("T3_TOPIC and PR are removed in log")
