################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from drpbase import abcmetricgenerator
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)


class MetricGeneratorWrongLabel(abcmetricgenerator.AbcMetricGenerator):
    def generate(self):
        # retruns 3 labels, while the configuration specifies 1
        return (["1", "2", "3"], 1)


class MetricGeneratorWrongGaugeValues(abcmetricgenerator.AbcMetricGenerator):
    def generate(self):
        # retruns string metric value, which cannot be converted to Gauge float
        return ([], "test")
