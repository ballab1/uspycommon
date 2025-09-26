################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler1(AbcMessageHandler):
    def handle_messages(self, message):
        if message.topic() == "testTopic4":
            print(
                f"handler1: Topic: {message.topic()} Partition: {message.partition()} Offset: {message.offset()}"
            )


class MessageHandler2(AbcMessageHandler):
    def handle_messages(self, message):
        if message.topic() == "testTopic5":
            print(
                f"handler2: Topic: {message.topic()} Partition: {message.partition()} Offset: {message.offset()}"
            )


class AClass:
    def my_method(self):
        return True
