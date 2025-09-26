################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
from drpbase import abcmetricgenerator
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)


class MetricGenerator2(abcmetricgenerator.AbcMetricGenerator):
    def generate(self):
        return ([], 2)
