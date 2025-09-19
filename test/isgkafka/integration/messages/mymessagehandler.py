################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import logging
from drpbase import constant
from drpbase import logger
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler1(AbcMessageHandler):
    def __init__(self) -> None:
        super().__init__()
        # making sure that configuration and logger is available in the constructor
        self.lgr = logging.getLogger(constant.LOGGER_NAME)
        assert (
            constant.CONFIGURATION["kafka"].get("consumers")[0]["group_id"]
            == "mr-be-gr-2"
        )
        self.lgr.info("Could successfully retrieve logger and the assertion passed")

    def handle_messages(self, message):
        if message.topic() == "testTopic4":
            self.lgr.info(
                f"handler1: Topic: {message.topic()} Partition: {message.partition()} "
                + f"Offset: {message.offset()} Message: {message.value()}"
            )
            # Apply a filter to main logger
            self.lgr.addFilter(
                logger.Bind({"MessageHandler1_PR_TOPIC": "Shown in main logger"})
            )


class MessageHandler2(AbcMessageHandler):
    def __init__(self):
        super().__init__()
        # Use child logger to keep log record change in this class
        self.child_logger = logging.getLogger(constant.LOGGER_NAME).getChild(
            "MessageHandler2"
        )

        # main logger in uspycommon
        self.main_logger = logging.getLogger(constant.LOGGER_NAME)

    def handle_messages(self, message):
        if message.topic() == "testTopic5":
            self.child_logger.addFilter(
                logger.Bind({"PR_TOPIC": message.topic(), "PR": "my_pr_number"})
            )

            self.child_logger.info(
                f"handler2: Topic: {message.topic()} Partition: {message.partition()} "
                + f"Offset: {message.offset()} Message: {message.value()}"
            )
            self.child_logger.info("PR_TOPIC and PR are added in log")
            # The PR_TOPIC and PR should be shown in the log due to binding.
            # log: {"message": "PR_TOPIC and PR are added in log", "PR_TOPIC": "testTopic5", "PR": "my_pr_number"}

            self.child_logger.addFilter(logger.Unbind(["PR_TOPIC"]))
            self.child_logger.info("PR_TOPIC is removed from log")
            # After unbinding PR_TOPIC, RP_TOPIC won't be included in log. Only PR is still there.
            # log: {"message": "PR_TOPIC is removed from log", "PR": "my_pr_number"}

            self.child_logger.addFilter(logger.Unbind(["PR"]))
            self.child_logger.info("PR is removed from log")
            # After unbinding PR, both PR_TOPIC and PR should have been removed in log
            # log: {"message": "PR is removed from log"}

            # Since MessageHandler1 binds MessageHandler1_PR_TOPIC to main logger,
            # the log record of main logger will be changed.
            self.main_logger.info("main_logger is logging")
            # Before MessageHandler1 binds MessageHandler1_PR_TOPIC to main logger,
            # log: {"message": "main_logger is logging"}

            # After MessageHandler1 receives a message and binds MessageHandler1_PR_TOPIC
            # to main logger, log is changed to
            # {"message": "main_logger is logging", "MessageHandler1_PR_TOPIC": "Shown in main logger"}
            # Child logger in this class should not be affected.
