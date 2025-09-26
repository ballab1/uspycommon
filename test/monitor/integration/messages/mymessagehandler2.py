################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler3(AbcMessageHandler):
    def handle_messages(self, message):
        if message.topic == "testTopic2":
            print(
                f"handler3: Topic: {message.topic} Partition: {message.partition} Offset: {message.offset}"
            )


class MessageHandler4(AbcMessageHandler):
    def handle_messages(self, message):
        if message.topic == "testTopic3":
            print(
                f"handler4: Topic: {message.topic} Partition: {message.partition} Offset: {message.offset}"
            )
