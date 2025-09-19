################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler3(AbcMessageHandler):
    def handle_messages(self, message):
        print("MessageHandler3 is running")


class MessageHandler4(AbcMessageHandler):
    def handle_messages(self, message):
        print("\nMessageHandler4 has exception")
        raise RuntimeError("MessageHandler4 Exception")


class AClass:
    def my_method(self):
        return True
