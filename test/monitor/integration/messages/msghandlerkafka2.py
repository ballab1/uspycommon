################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import time
import logging
from isgkafka.messagehandler import AbcMessageHandler
from drpbase import constant


class MessageHandler2(AbcMessageHandler):
    def __init__(self):
        self.lgr = logging.getLogger(constant.LOGGER_NAME)

    def handle_messages(self, message):
        self.lgr.info("Handler2 called.")
        if message.value["handler_id"] == 2:
            if message.value["exception"]:
                raise Exception("Handler2 throwing exception as requested")
            sleep_time = message.value["sleep"]
            self.lgr.info("Handler2 going to sleep %s secs", sleep_time)
            time.sleep(message.value["sleep"])
        else:
            self.lgr.info("Handler2  going to sleep for %d secs", 1)
            time.sleep(1)
