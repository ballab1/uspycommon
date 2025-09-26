################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import abc


class AbcMetricGenerator(object):
    """During each scrape, Prometheus will call the function `generate` to retrieve the metric
    value.
    """

    @abc.abstractmethod
    def generate(self):
        """Returns a tuple ([label_values],metric_value)
        The array size and the values must match the specification in the configuration.
        """
        raise NotImplementedError("Please implement the value generator")
