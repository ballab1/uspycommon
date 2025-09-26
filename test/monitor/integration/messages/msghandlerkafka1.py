################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import time
import logging
from isgkafka.messagehandler import AbcMessageHandler
from drpbase import constant


class MessageHandler1(AbcMessageHandler):
    def __init__(self):
        self.lgr = logging.getLogger(constant.LOGGER_NAME)

    def handle_messages(self, message):
        self.lgr.info("Handler1 called.")
        if message.value["handler_id"] == 1:
            if message.value["exception"]:
                raise Exception("Handler1 throwing exception as requested")
            sleep_time = message.value["sleep"]
            self.lgr.info("Handler1 going to sleep %s secs", sleep_time)
            time.sleep(sleep_time)
        else:
            self.lgr.info("Handler1  going to sleep for %d secs", 1)
            time.sleep(1)
