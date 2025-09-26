################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler6(AbcMessageHandler):
    def handle_messages(self, message):
        print(
            f"handler6: Topic: {message.topic()} Partition: {message.partition()} "
            + f"Offset: {message.offset()} Message: {message.value()}"
        )
