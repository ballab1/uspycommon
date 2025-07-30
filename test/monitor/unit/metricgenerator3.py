################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from drpbase import abcmetricgenerator
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)


class MetricGenerator3(abcmetricgenerator.AbcMetricGenerator):
    counter = 2

    def generate(self):
        return (["1"], 3)
