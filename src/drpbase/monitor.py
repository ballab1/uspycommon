################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import importlib
import logging
from prometheus_client import (
    REGISTRY,
    PROCESS_COLLECTOR,
    PLATFORM_COLLECTOR,
    GC_COLLECTOR,
)
from prometheus_client.core import CounterMetricFamily
from prometheus_client.core import GaugeMetricFamily
from prometheus_client import start_http_server

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from drpbase import constant

GAUGE = "GAUGE"
COUNTER = "COUNTER"
HISTOGRAM = "HISTOGRAM"


class Monitor:
    """Unregisters default collectors, registers specified collectors, and starts
    http server at the specified port.
    """

    def __init__(self, config, logger_name=constant.LOGGER_NAME):
        self.metric_classes = {}
        self.logger = logging.getLogger(logger_name)
        if config.get("collect_default_metric", None) is not None:
            if config["collect_default_metric"] is False:
                self.logger.info("De-registering default metrics collection")
                REGISTRY.unregister(PROCESS_COLLECTOR)
                REGISTRY.unregister(PLATFORM_COLLECTOR)
                REGISTRY.unregister(GC_COLLECTOR)
            else:
                self.logger.info("Default metrics will be collected.")
        else:
            self.logger.error("collect_default_metric field not soecified.")
            self.logger.error(config)

        if config.get("port", None) is not None:
            self.logger.info(
                "Starting prometheus http server at port %d", config["port"]
            )
            start_http_server(config["port"])
        else:
            self.logger.error("No monitoring server started. Port not specified.")

        # for coll in list(REGISTRY._collector_to_names.keys()):
        #     REGISTRY.unregister(coll)

    def register_metrics(self, metrics):
        self.logger.info("Registering metrics")
        for metric in metrics:
            # load module
            module = importlib.import_module(metric["collector"]["module"])
            # from the input derived class name, load the specified class from the module
            derived_class = getattr(module, metric["collector"]["class"])
            self.logger.info(
                "Loaded class %s from module %s",
                metric["collector"]["class"],
                metric["collector"]["module"],
            )

            metric_cls_inst = derived_class()
            dc = DataCollector(
                self.logger,
                metric["name"],
                metric["description"],
                metric["labels"],
                metric["type"],
                metric_cls_inst,
            )
            self.metric_classes[metric["collector"]["class"]] = metric_cls_inst
            REGISTRY.register(dc)

    def get_metric_classes(self):
        return self.metric_classes


class DataCollector:
    """The collector object which is created per specification and registered with Prometheus"""

    def __init__(self, lgr, name, description, labels, p_type, supplier_class):
        self.m_n = name
        self.m_des = description
        self.m_labels = labels
        self.m_type = p_type
        self.m_sc = supplier_class
        self.m_logger = lgr
        self.m_logger.info(
            "Created data collector name=%s, description=%s, labels=%s, type=%s",
            self.m_n,
            self.m_des,
            self.m_labels,
            self.m_type,
        )

    def collect(self):
        """Called by Prometheus to collect metrics"""
        if self.m_type == GAUGE:
            val = GaugeMetricFamily(self.m_n, self.m_des, labels=self.m_labels)
            retrieved_value = self._retrieve_value()
            val.add_metric(retrieved_value[0], retrieved_value[1])
            yield val
        if self.m_type == COUNTER:
            val = CounterMetricFamily(self.m_n, self.m_des, labels=self.m_labels)
            retrieved_value = self._retrieve_value()
            val.add_metric(retrieved_value[0], retrieved_value[1])
            yield val

    def _retrieve_value(self):
        retrieved_value = self.m_sc.generate()

        if len(self.m_labels) != len(retrieved_value[0]):
            self.m_logger.error(
                "number of retrieved label values do not match label numbers"
            )
            return self._handle_error()

        try:
            if self.m_type == GAUGE:
                _ = float(retrieved_value[1])
        except Exception as exp:
            self.m_logger.error(
                "Exception type: %s, Message: %s", exp.__class__.__name__, str(exp)
            )
            return self._handle_error()

        self.m_logger.debug(
            "name=%s, label_vals=[%s], val=%s",
            self.m_n,
            ",".join(map(str, retrieved_value[0])),
            retrieved_value[1],
        )
        return retrieved_value

    def _handle_error(self):
        error_value = []
        error_labels = []
        for i in range(0, len(self.m_labels)):
            error_labels.append("error")
        error_value.append(tuple(error_labels))
        error_value.append(constant.DEFAULT_WRONG_GAUGE_METRIC_VALUE)
        self.m_logger.error(
            "name=%s, label_vals=[%s], val=%s",
            self.m_n,
            ",".join(map(str, error_value[0])),
            error_value[1],
        )
        return error_value
