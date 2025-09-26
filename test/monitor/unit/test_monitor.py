#!/usr/bin/env python3
################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
from prometheus_client import REGISTRY

import pytest
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.drpbase import logger, constant, monitor


def setup_module():
    logger.setup_logger(constant.LOGGER_NAME, "DEBUG")


@pytest.fixture(autouse=True)
def run_around_tests():
    pass


def teardown_module():
    pass


def test_collect_default_ignore_user_metrics(caplog):
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    cfg_file = os.path.abspath(
        os.path.join(top, "collect_default_ignore_user_metrics.yml")
    )
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    _ = monitor.Monitor(cfg["framework"]["monitor"])

    collected_metric = REGISTRY.collect()
    metric_count = 0
    for metric in collected_metric:
        metric_count = metric_count + 1
    # assert the relevant log capture
    assert "Default metrics will be collected." in caplog.text
    assert "Starting prometheus http server at port 8002" in caplog.text
    # Currently the following metrics are collected by default.
    # 1. 'python_gc_objects_collected_total'
    # 2. 'python_gc_objects_uncollectable_total'
    # 3. 'python_gc_collections_total'
    # 4. 'python_info'
    # 5. 'process_virtual_memory_bytes'
    # 7. 'process_start_time_seconds'
    # 8. 'process_cpu_seconds_total'
    # 9. 'process_open_fds'
    # 10.'process_max_fds'


def test_collect_default_and_user_metrics(caplog):
    # We add an extra metric test_metric1
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    cfg_file = os.path.abspath(
        os.path.join(top, "collect_default_and_user_metrics.yml")
    )
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    mn = monitor.Monitor(cfg["framework"]["monitor"])
    mn.register_metrics(cfg["framework"]["monitor"]["metrics"])
    metric_count = 0
    test_metric1_found = False
    collected_metric = REGISTRY.collect()
    for metric in collected_metric:
        metric_count = metric_count + 1
        for sample in metric.samples:
            if sample.name == "test_metric1":
                assert sample.labels == {"l1": "1", "l2": "2"}
                assert sample.value == 1
                assert sample.timestamp is None
                test_metric1_found = True
    assert test_metric1_found is True
    assert "Default metrics will be collected." in caplog.text
    assert "Starting prometheus http server at port 8001" in caplog.text


def test_ignore_default_collect_user_metrics(caplog):
    # We de-register default metric and register extra 2 metrics test_metric2, test_metric3
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    cfg_file = os.path.abspath(
        os.path.join(top, "ignore_default_collect_user_metrics.yml")
    )
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    mn = monitor.Monitor(cfg["framework"]["monitor"])
    mn.register_metrics(cfg["framework"]["monitor"]["metrics"])
    collected_metric = REGISTRY.collect()
    test_metrics = {
        "test_metric2": {"labels": {}, "value": 2, "found": False},
        "test_metric3_total": {"labels": {"l1": "1"}, "value": 3, "found": False},
    }
    for metric in collected_metric:
        for sample in metric.samples:
            if sample.name in test_metrics.keys():
                assert sample.labels == test_metrics[sample.name]["labels"]
                assert sample.value == test_metrics[sample.name]["value"]
                assert sample.timestamp is None
                assert test_metrics[sample.name]["found"] is False
                test_metrics[sample.name]["found"] = True
    for metric in test_metrics.keys():
        assert test_metrics[metric]["found"] is True
    assert "Starting prometheus http server at port 8003" in caplog.text
    assert "Registering metrics" in caplog.text
    assert "Loaded class MetricGenerator2 from module metricgenerator2" in caplog.text
    assert "Loaded class MetricGenerator3 from module metricgenerator3" in caplog.text
    assert (
        "Created data collector name=test_metric2, description=example metric2 in the ms, labels=[], type=GAUGE"
        in caplog.text
    )
    assert (
        "Created data collector name=test_metric3, description=example metric3 in ms, labels=['l1'], type=COUNTER"
        in caplog.text
    )
    assert "name=test_metric2, label_vals=[], val=2" in caplog.text
    assert "name=test_metric3, label_vals=[1], val=3" in caplog.text


def test_collect_wrong_metrics(caplog):
    # We de-register default metric and register extra 2 metrics test_metric2, test_metric3
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    cfg_file = os.path.abspath(
        os.path.join(top, "ignore_default_collect_wrong_user_metrics.yml")
    )
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    mn = monitor.Monitor(cfg["framework"]["monitor"])
    mn.register_metrics(cfg["framework"]["monitor"]["metrics"])
    assert "number of retrieved label values do not match label numbers" in caplog.text
    assert "could not convert string to float: 'test'" in caplog.text


def test_get_metric_classes():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "."))
    cfg_file = os.path.abspath(os.path.join(top, "metric_generator_config.yml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    mn = monitor.Monitor(cfg["framework"]["monitor"])
    mn.register_metrics(cfg["framework"]["monitor"]["metrics"])
    monitor_class_dict = mn.get_metric_classes()

    assert type(monitor_class_dict) == dict
    assert [
        key for key in monitor_class_dict.keys() if key.startswith("MetricGenerator2")
    ][0] == "MetricGenerator2"
    assert [
        key for key in monitor_class_dict.keys() if key.startswith("MetricGenerator3")
    ][0] == "MetricGenerator3"
    assert (
        type(
            [
                value
                for value in monitor_class_dict.values()
                if type(value).__name__.startswith("MetricGenerator2")
            ][0]
        ).__name__
        == "MetricGenerator2"
    )
    assert (
        type(
            [
                value
                for value in monitor_class_dict.values()
                if type(value).__name__.startswith("MetricGenerator3")
            ][0]
        ).__name__
        == "MetricGenerator3"
    )
    assert (
        str(
            type(
                [
                    value
                    for value in monitor_class_dict.values()
                    if type(value).__name__.startswith("MetricGenerator2")
                ][0]
            )
        )
        == "<class 'metricgenerator2.MetricGenerator2'>"
    )
    assert (
        str(
            type(
                [
                    value
                    for value in monitor_class_dict.values()
                    if type(value).__name__.startswith("MetricGenerator3")
                ][0]
            )
        )
        == "<class 'metricgenerator3.MetricGenerator3'>"
    )
