################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import abc


class AbcMessageHandler(metaclass=abc.ABCMeta):
    def __call__(self, message):
        self.handle_messages(message)

    @abc.abstractmethod
    def handle_messages(self, message):
        raise NotImplementedError
