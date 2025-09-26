################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
    mymessagefilter.py
    -----------------

    The MessageFilter calss implements AbcMessageFilter class and provides
    a filter function to be used in isgkafka consumer.
"""
import logging
from isgkafka.messagefilter import AbcMessageFilter
from drpbase import constant


class MessageFilter1(AbcMessageFilter):
    """
    A MessageFilter class that implements AbcMessageFilter
    """

    def __init__(self):
        self.lgr = logging.getLogger(constant.LOGGER_NAME)

    def filter_messages(self, message):
        self.lgr.info("Filter3 called.")
        return True
