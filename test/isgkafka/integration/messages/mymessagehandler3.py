################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler5(AbcMessageHandler):

    def __init__(self, service):
        self.service = service

    def handle_messages(self, message):
        if message.topic() == "testTopic1":
            print(
                f"handler5: Topic: {message.topic()} Partition: {message.partition()} "
                + f"Offset: {message.offset()} Message: {message.value()}"
            )

            self.service.print_name()
            self.service.print_type()
