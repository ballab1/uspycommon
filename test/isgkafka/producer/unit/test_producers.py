#!/usr/bin/env python3
################################################################################
# Copyright (c) 2020-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import pytest
import yaml

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../src"))
)
from drpbase.producers import KProducers


@pytest.fixture(name="config_dict")
def fixture_config_dict():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r", encoding="utf8") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    return cfg["kafka"]


@pytest.fixture(name="producers")
def fixture_producers(mocker, config_dict):
    mocker.patch("isgkafka.producer.Producer")
    mocker.patch("isgkafka.producer.KProducer._validate_topic_partition")
    kproducers = KProducers(config_dict)
    return kproducers


def test_no_producer(config_dict):
    config_dict["producers"] = None
    with pytest.raises(
        ValueError, match=r"Tried to create KProducer without supplying configuration."
    ):
        # Init. KProducers without producer defined
        KProducers(config_dict)


def test_no_producer_name(config_dict):
    config_dict["producers"][0]["name"] = None
    with pytest.raises(ValueError, match=r"Producer name is required"):
        # Init. KProducers without producer name defined
        KProducers(config_dict)


def test_creation_exception(config_dict):
    with pytest.raises(Exception):
        # Init. KProducers with no existing kafka server
        KProducers(config_dict)


def test_get_by_name(producers):
    assert "producer1" == producers.get_by_name("producer1").name
    assert "producer2" == producers.get_by_name("producer2").name
    assert None is producers.get_by_name("producer3")


def test_close_producer(producers, caplog):
    producers.close_producer("producer1")
    assert None is producers.get_by_name("producer1")
    producers.close_producer("producer3")
    assert "Producer producer3 not found" in caplog.text
    producers.close_producers()
    assert None is producers.get_by_name("producer2")
    producers.producers = None
    producers.close_producers()
