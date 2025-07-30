################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from drpbase import abcmetricgenerator


class MetricGenerator3(abcmetricgenerator.AbcMetricGenerator):
    counter = 0

    def generate(self):
        MetricGenerator3.counter = MetricGenerator3.counter + 1
        return (["1"], MetricGenerator3.counter)
