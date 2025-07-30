#!/usr/bin/env python3
################################################################################
# Copyright (c) 2020-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import pytest
import yaml
import json
from confluent_kafka.admin import ClusterMetadata
from confluent_kafka.admin import TopicMetadata
from confluent_kafka.admin import PartitionMetadata
from confluent_kafka.admin import KafkaError

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../src"))
)
from isgkafka.producer import KProducer
from drpbase import constant

PRODUCER = "isgkafka.producer.Producer"
VALIDATE_TOPIC_PARTITION = "isgkafka.producer.KProducer._validate_topic_partition"
GET_MAX_PARTITION_NUMBER = "isgkafka.producer.KProducer._get_max_partition_number"


@pytest.fixture(name="config_dict")
def fixture_config_dict():
    constant.MAX_ATTEMPTS = 1
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r", encoding="utf8") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    producer_cfg = cfg["kafka"].get("producers", None)[0]
    producer_cfg["bootstrap_servers"] = cfg["kafka"].get("bootstrap_servers", None)
    constant.KAFKA_VALIDATION_TIMEOUT = 1.0

    return producer_cfg


@pytest.fixture(name="init_producer")
def fixture_init_producer(config_dict, mocker):
    mocker.patch(PRODUCER)
    mocker.patch(VALIDATE_TOPIC_PARTITION)

    kproducer = KProducer(config_dict)

    return kproducer


@pytest.mark.parametrize(
    "topics",
    [
        ([{"name": "testTopic1", "partition": 1}]),
        ([{"name": "testTopic2"}]),
    ],
)
def test_validate_topic_partition(mocker, config_dict, topics):
    mocker.patch(GET_MAX_PARTITION_NUMBER, return_value=12)
    mocker.patch(PRODUCER)

    kproducer = KProducer(config_dict)
    kproducer._max_validated_topics_items = 1
    kproducer._validate_topic_partition(topics)


@pytest.mark.parametrize(
    "topics",
    [
        ([{"name": "", "partition": 1}]),  # missing name
        ([{"name": "testTopic5", "partition": 20}]),  # partition is too big
    ],
)
def test_validate_topic_partition_exception(mocker, config_dict, topics):
    mocker.patch(PRODUCER)
    mocker.patch(GET_MAX_PARTITION_NUMBER, return_value=12)

    kproducer = KProducer(config_dict)
    with pytest.raises(ValueError):
        kproducer._validate_topic_partition(topics)


def test_open_exception(mocker, config_dict):
    mocker.patch(PRODUCER, side_effect=ValueError("wrong parameters"))

    with pytest.raises(ValueError, match="wrong parameters"):
        KProducer(config_dict)


def test_close(init_producer):
    init_producer.close()


def test_close_exception(mocker, caplog, init_producer):
    mocker.patch.object(init_producer, "flush", side_effect=Exception)

    init_producer.close()
    assert "Cannot close producer" in caplog.text


def test_get_max_partition_number_exception(mocker, init_producer, caplog):
    mocker.patch.object(init_producer.producer, "list_topics", side_effect=Exception)

    with pytest.raises(Exception):
        init_producer._get_max_partition_number("testTopic")

    assert "Error while checking for Topic: testTopic." in caplog.text


def test_get_max_partition_number_unknown_topic(mocker, init_producer):
    # Create mock PartitionMetadata objects
    mocked_partition1 = mocker.Mock(
        spec=PartitionMetadata,
        id=0,
        error=KafkaError(0),
        leader=0,
        replicas=[0, 1, 2],
        isr=[0, 1, 2],
    )

    # Create mock TopicMetadata object
    mocked_topic_metadata = mocker.Mock(
        spec=TopicMetadata,
        topic="testTopic",
        error=KafkaError(KafkaError.UNKNOWN_TOPIC_OR_PART),
        partitions=[mocked_partition1],
    )

    # Create mock ClusterMetadata object
    mocked_cluster_metadata = mocker.Mock(
        spec=ClusterMetadata, topics={"testTopic": mocked_topic_metadata}, cluster_id=1
    )

    mocker.patch.object(
        init_producer.producer, "list_topics", return_value=mocked_cluster_metadata
    )
    with pytest.raises(ValueError, match="Topic: testTopic doesn't exist"):
        init_producer._get_max_partition_number("testTopic")


def test_get_max_partition_number(mocker, init_producer):
    # Create mock PartitionMetadata objects
    mocked_partition1 = mocker.Mock(
        spec=PartitionMetadata,
        id=0,
        error=KafkaError(0),
        leader=0,
        replicas=[0, 1, 2],
        isr=[0, 1, 2],
    )

    mocked_partition2 = mocker.Mock(
        spec=PartitionMetadata,
        id=1,
        error=KafkaError(0),
        leader=1,
        replicas=[1, 2, 3],
        isr=[1, 2, 3],
    )

    # Create mock TopicMetadata object
    mocked_topic_metadata = mocker.Mock(
        spec=TopicMetadata,
        topic="testTopic",
        error=KafkaError(2),
        partitions=[mocked_partition1, mocked_partition2],
    )

    # Create mock ClusterMetadata object
    mocked_cluster_metadata = mocker.Mock(
        spec=ClusterMetadata, topics={"testTopic": mocked_topic_metadata}, cluster_id=1
    )

    mocker.patch.object(
        init_producer.producer, "list_topics", return_value=mocked_cluster_metadata
    )

    assert 2 == init_producer._get_max_partition_number("testTopic")


def test_no_topics(config_dict, mocker, caplog):
    mocker.patch(PRODUCER)
    mocker.patch(VALIDATE_TOPIC_PARTITION)
    config_dict.pop("topics")

    producer = KProducer(config_dict)
    producer.send({"message": "message"})
    assert "Please verify a topic is defined and it exists on server" in caplog.text


def test_no_bootstrap_server(config_dict):
    config_dict["bootstrap_servers"] = None
    with pytest.raises(ValueError, match="Value of key: bootstrap_servers not found"):
        # Init. Kconsumer without bootstrap_servers
        KProducer(config_dict)


def test_wrong_bootstrap_server(config_dict):
    with pytest.raises(ValueError, match="NoBrokersAvailable"):
        # Init. KProducer with wrong bootstrap_servers
        KProducer(config_dict)


def test_no_producer():
    config_dict = None
    with pytest.raises(
        Exception, match="Tried to create KProducer without supplying configuration."
    ):
        # Init. KProducer without producer defined
        KProducer(config_dict)


def test_send_exception(mocker, init_producer):
    mocker.patch.object(init_producer.producer, "produce", side_effect=Exception())
    uuid = init_producer.send({"message": "message"})
    assert uuid is None


def test_send(init_producer, caplog):
    assert init_producer.send({"message": "message"}) is not None
    assert (
        init_producer.send({"message": "message"}, [{"name": "testTopic2"}]) is not None
    )
    assert init_producer.send(json.dumps({"message": "message"})) is not None

    init_producer.send("bad message")
    assert "Failed with error" in caplog.text
