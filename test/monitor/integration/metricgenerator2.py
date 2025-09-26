from drpbase import abcmetricgenerator
import random


class MetricGenerator2(abcmetricgenerator.AbcMetricGenerator):
    def generate(self):
        num = random.randrange(1, 10)
        if num == 2 or num == 8:
            return ([], "wrong_labels")
        elif num == 4:
            return (["val1", "val2"], "wrong_val")
        else:
            return (["val1", "val2"], num)
