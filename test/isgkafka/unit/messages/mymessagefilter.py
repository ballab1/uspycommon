################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
    mymessagefilter.py
    -----------------

    The MessageFilter class implements AbcMessageFilter class and provides
    a filter function to be used in isgkafka consumer.
"""
from isgkafka.messagefilter import AbcMessageFilter


class AClass:
    def my_method(self):
        return True


class MessageFilter(AbcMessageFilter):
    """
    A MessageFilter class that implements AbcMessageFilter
    """

    def filter_messages(self, message):
        if message.topic() == "testTopic0" or message.topic() == "testTopic2":
            return True

        return False
