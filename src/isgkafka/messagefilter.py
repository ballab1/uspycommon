################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import abc


class AbcMessageFilter(metaclass=abc.ABCMeta):
    def __call__(self, message):
        return self.filter_messages(message)

    @abc.abstractmethod
    def filter_messages(self, message):
        raise NotImplementedError
