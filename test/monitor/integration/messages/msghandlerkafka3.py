################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import time
import logging
from isgkafka.messagehandler import AbcMessageHandler
from drpbase import constant


class MessageHandler3(AbcMessageHandler):
    def __init__(self):
        self.lgr = logging.getLogger(constant.LOGGER_NAME)
        self.kproducer1 = constant.PRODUCERS.get_by_name("producer1")

    def handle_messages(self, message):
        if message.value.get("exception", None) == False:
            self.lgr.info("handler3 called. producer will send well formed message")
            self.kproducer1.send({"message": "test", "exception": "false"})
        elif message.value.get("exception", None) == True:
            self.lgr.info("handler3 called. producer will throw exception")
            self.kproducer1.send("malformed message")
        else:
            self.lgr.info("handler3 called. triggered by producer message. no op")
