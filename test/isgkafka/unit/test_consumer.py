#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import logging
from dataclasses import dataclass
from typing import List

import pytest
import yaml
import re
from unittest.mock import call

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from isgkafka.messagehandler import AbcMessageHandler
from isgkafka.consumer import KConsumer
from drpbase import constant
from drpbase.jobmanager import JobManager
from confluent_kafka import TopicPartition
from confluent_kafka import Message
from confluent_kafka import OFFSET_STORED
from confluent_kafka import OFFSET_BEGINNING

from messages.mymessagefilter import MessageFilter
from messages.mymessagehandler import MessageHandler1
from messages.mymessagehandler2 import MessageHandler3
from messages.mymessagehandler2 import MessageHandler4


CONSUMER = "isgkafka.consumer.Consumer"
PRODUCER = "isgkafka.consumer.KProducer"
GET_OFFSET = "isgkafka.consumer.KConsumer._get_watermark_offsets"
COMMIT = "isgkafka.consumer.Consumer.commit"
GET_MAX_PARTITION_NUMBER = "isgkafka.consumer.KConsumer._get_max_partition_number"
JSON_LOADS = "isgkafka.consumer.json.loads"
PAUSE = "isgkafka.consumer.KConsumer.pause"
RESUME = "isgkafka.consumer.KConsumer.resume"
GET_ACTIVE_JOB_COUNT = "drpbase.jobmanager.JobManager.get_active_job_count"


@pytest.fixture
def config_dict():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    constant.KAFKA_VALIDATION_TIMEOUT = 1.0

    return cfg


@pytest.fixture
def consumer_config_dict_with_sec_options(config_dict):
    """A fixture to encapsulate a correct example of secure Kafka configuration."""
    consumer_config = config_dict["kafka"].get("consumers")[0]
    consumer_config["bootstrap_servers"] = ["10.10.10.10:9093"]
    consumer_config["ssl_ca_location"] = "/foo/kafka_dellca2018-bundle.crt"
    consumer_config["ssl_certificate_location"] = "/foo/kafka_certificate.pem"
    consumer_config["ssl_key_location"] = "/foo/kafka_private_key.pem"

    return consumer_config


@pytest.fixture
def kafka_messages(mocker):
    key_ret_val = b'my_key'

    def get_key():
        nonlocal key_ret_val
        return key_ret_val

    def set_key(value):
        nonlocal key_ret_val
        key_ret_val = value

    value_return_val = b'{"message": "DRP"}'

    def get_value():
        nonlocal value_return_val
        return value_return_val

    def set_value(value):
        nonlocal value_return_val
        value_return_val = value

    mocked_message = mocker.Mock(spec=Message)
    mocked_message.error.return_value = None
    mocked_message.topic.return_value = "testTopic2"
    mocked_message.key = get_key
    mocked_message.set_key = set_key
    mocked_message.value = get_value
    mocked_message.set_value = set_value
    mocked_message.partition.return_value = 0
    mocked_message.offset.return_value = 10

    return mocked_message


@pytest.fixture
def common_mocks(mocker):
    mocker.patch(CONSUMER)
    mocker.patch(PRODUCER)
    mocker.patch(PAUSE)
    mocker.patch(RESUME)
    mocker.patch("threading.Thread.start")
    constant.MAX_ATTEMPTS = 1


@pytest.fixture
def init_first_consumer(common_mocks):
    def factory(conf):
        conf["kafka"].get("consumers")[0]["bootstrap_servers"] = conf["kafka"].get("bootstrap_servers")
        kconsumer = KConsumer(conf["kafka"].get("consumers")[0])
        kconsumer._init_consumer()
        return kconsumer

    yield factory


@pytest.fixture
def init_consumer(config_dict, init_first_consumer):
    return init_first_consumer(config_dict)


@dataclass
class HandlerConf:
    handler_instance: AbcMessageHandler
    mock_name: str
    raise_exception: bool = False


@pytest.fixture
def consumer_mocker(init_consumer, mocker, kafka_messages):
    def add_mocks_to_consumer(
            consumer: KConsumer = None,
            message_value_deserialization_raises_ex: bool = False,
            message_key_deserialization_raises_ex: bool = False,
            filter_raise_ex: bool = False,
            filter_returns_false: bool = False,
            handler_raise_ex: bool = False,
            handler_confs: List[HandlerConf] = None,
    ):
        c = consumer if consumer else init_consumer
        mocker.patch(GET_OFFSET, return_value=(0, 12))

        # bundling the mocks into this one
        manager = mocker.Mock()

        mock_commit = mocker.patch.object(c, "_commit")
        manager.attach_mock(mock_commit, "mock_commit")

        if message_value_deserialization_raises_ex:
            kafka_messages.set_value(b"123 invalid json")
        if message_key_deserialization_raises_ex:
            kafka_messages.set_key("this is an invalid kafka key")

        # mock-out filters
        msg_filter = MessageFilter()
        c.register_filter(msg_filter)
        mock_filter_message = mocker.patch.object(
            c._msg_filter, "filter_messages",
            side_effect=Exception if filter_raise_ex else None,
            return_value=False if filter_returns_false else True,
        )
        manager.attach_mock(mock_filter_message, "mock_filter_message")

        # mock-out handlers
        msg_handlers = list()

        if not handler_confs:
            handler_confs = [HandlerConf(
                handler_instance=MessageHandler1(),
                mock_name="mock_handle_messages",
                raise_exception=True if handler_raise_ex else False
            )]
        elif handler_raise_ex:
            raise AttributeError("Invalid param combination: handler_raise_ex should not be used with handler_confs")

        for hc in handler_confs:
            mock_handle_messages = mocker.patch.object(
                hc.handler_instance, "handle_messages",
                side_effect=Exception if hc.raise_exception else None)
            manager.attach_mock(mock_handle_messages, hc.mock_name)
            msg_handlers.append(hc.handler_instance)

        c.register_handlers(msg_handlers)

        return manager

    yield add_mocks_to_consumer


@pytest.fixture
def job_manager(config_dict, mocker):
    constant.JOB_MANAGER_NAME = config_dict["jobmanager"]["job_manager_name"]
    constant.KEEPING_FAILED_JOB_TIME = config_dict["jobmanager"][
        "keeping_failed_job_time"
    ]
    constant.KEEPING_SUCCEEDED_JOB_TIME = config_dict["jobmanager"][
        "keeping_succeeded_job_time"
    ]
    constant.DEV_NAMESPACE = config_dict["jobmanager"]["dev_namespace"]
    constant.JOB_MAX_RUNNING_TIME = config_dict["jobmanager"]["job_max_running_time"]
    constant.MAX_PARALLEL_JOB = config_dict["jobmanager"]["max_parallel_job"]

    mocker.patch("drpbase.jobmanager.config")
    mocker.patch("drpbase.jobmanager.client.BatchV1Api")
    return JobManager(config_dict["jobmanager"]["jobs"])


@pytest.mark.parametrize(
    "topic_name, partitions, max_partition_number, topic_partitions, expected",
    [
        (
            "test_topic_name",
            [{"number": 1, "offset": 5}],
            10,
            [],
            [TopicPartition("test_topic_name", 1, 5)],
        ),
        (
            "test_topic_name",
            [{"number": 0}],
            10,
            [],
            [TopicPartition("test_topic_name", 0, OFFSET_STORED)],
        ),
        (
            "test_topic_name",
            [{"number": 0, "offset": -1}],
            10,
            [],
            [TopicPartition("test_topic_name", 0, OFFSET_STORED)],
        ),
        # If offset is out of range, expect OFFSET_BEGINNING because of auto_offset_reset is "earliest"
        (
            "test_topic_name",
            [{"number": 0, "offset": 50}],
            10,
            [],
            [TopicPartition("test_topic_name", 0, OFFSET_BEGINNING)],
        ),
    ],
)
def test_get_topic_partitions(
    init_consumer,
    topic_name,
    partitions,
    max_partition_number,
    topic_partitions,
    expected,
    mocker,
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    init_consumer._get_topic_partitions(
        topic_name, partitions, max_partition_number, topic_partitions
    )

    assert topic_partitions == expected


@pytest.mark.parametrize(
    "topic_name, partitions, max_partition_number, topic_partitions",
    [
        ("test_topic_name", [{"number": 12, "offset": 5}], 10, []),
    ],
)
def test_get_topic_partitions_exception(
    mocker,
    init_consumer,
    topic_name,
    partitions,
    max_partition_number,
    topic_partitions,
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))

    with pytest.raises(LookupError):
        init_consumer._get_topic_partitions(
            topic_name, partitions, max_partition_number, topic_partitions
        )


def test_get_topics_name(mocker, config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    mocker.patch(CONSUMER)

    kconsumer = KConsumer(config_dict["kafka"].get("consumers")[0])
    kconsumer._init_consumer()
    _, topic_names = kconsumer._get_topics()

    expected_topic_names = ["testTopic2", "testTopic4"]
    assert expected_topic_names == topic_names


def test_get_topics(mocker, config_dict):
    config_dict["kafka"].get("consumers")[1]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    mocker.patch(CONSUMER)
    mocker.patch(GET_MAX_PARTITION_NUMBER, return_value=12)
    mocker.patch(GET_OFFSET, return_value=(0, 200))

    kconsumer = KConsumer(config_dict["kafka"].get("consumers")[1])
    topic_partitions, _ = kconsumer._get_topics()

    expected_topic_partitions = [
        TopicPartition("testTopic5", 0, -1),
        TopicPartition("testTopic5", 1, 10),
        TopicPartition("testTopic3", 0, 1),
        TopicPartition("testTopic3", 1, 2),
    ]

    assert expected_topic_partitions == topic_partitions


@pytest.mark.parametrize(
    "topics",
    [
        [
            {"name": "testTopic", "partitions": [{"number": 1, "offset": 2}]},
            {"name": "testTopic2"},
        ],
        [
            {"name": "testTopic"},
            {"name": "testTopic2", "partitions": [{"number": 1, "offset": 2}]},
        ],
    ],
)
def test_get_topics_exception(mocker, config_dict, topics):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    config_dict["kafka"].get("consumers")[0]["topics"] = topics
    mocker.patch(CONSUMER)
    mocker.patch(GET_MAX_PARTITION_NUMBER, return_value=12)

    with pytest.raises(ValueError):
        kconsumer = KConsumer(config_dict["kafka"].get("consumers")[0])
        kconsumer.start()


def test_no_bootstrap_server(config_dict):
    with pytest.raises(ValueError, match="Value of key: bootstrap_servers not found"):
        # Init. Kconsumer without bootstrap_servers
        KConsumer(config_dict["kafka"].get("consumers")[0])


def test_wrong_bootstrap_server(mocker, config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    with pytest.raises(Exception, match="NoBrokersAvailable"):
        # Init. Kconsumer with wrong bootstrap_servers
        kconsumer = KConsumer(config_dict["kafka"].get("consumers")[0])
        kconsumer._init_consumer()


def test_no_topics(config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    config_dict["kafka"].get("consumers")[0]["topics"] = {}
    with pytest.raises(ValueError, match=r"topics isn't a List"):
        # Init. Kconsumer without topics
        KConsumer(config_dict["kafka"].get("consumers")[0])


def test_mix_bootstrap_servers(config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = [
        "10.10.10.10:9092",
        "10.10.10.10:9093",
    ]
    with pytest.raises(
        ValueError,
        match=r"Both non-ssl port 9092 and ssl port 9093 is found, which is not allowed",
    ):
        # Init. Kconsumer with mix bootstrap servers
        KConsumer(config_dict["kafka"].get("consumers")[0])


def test_bootstrap_servers(mocker, config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = ["10.10.10.10:9093"]
    mocker.patch(CONSUMER)
    mocker.patch(PAUSE)
    mocker.patch(RESUME)
    kconsumer = KConsumer(config_dict["kafka"].get("consumers")[0])
    kconsumer._init_consumer()


def test_get_offset(init_consumer, mocker):
    EXPECTED_VALUE = (10, 20)
    mocker.patch.object(
        init_consumer.consumer, "get_watermark_offsets", return_value=EXPECTED_VALUE
    )
    assert EXPECTED_VALUE == init_consumer._get_watermark_offsets(
        TopicPartition("testTopic", 1)
    )

    mocker.patch.object(
        init_consumer.consumer, "get_watermark_offsets", side_effect=Exception
    )
    with pytest.raises(Exception):
        init_consumer._get_watermark_offsets(TopicPartition("testTopic", 1))


def test_get_max_partition_number_exception(init_consumer, mocker, caplog):
    mocker.patch.object(init_consumer.consumer, "list_topics", side_effect=Exception)
    with pytest.raises(Exception):
        init_consumer._get_max_partition_number("testTopic")

    assert "Error while checking for Topic" in caplog.text


def test_set_topics_name(init_consumer, mocker):
    mocker.patch.object(init_consumer.consumer, "subscribe", side_effect=lambda x: None)
    topic_names = {"testTopic1", "testTopic2"}
    init_consumer._set_topics({}, topic_names)

    init_consumer.consumer.subscribe.assert_called_once_with(topic_names)


def test_set_topics_partition(init_consumer, mocker):
    mocker.patch.object(init_consumer.consumer, "assign", side_effect=lambda x: None)
    topic_partitions = [
        TopicPartition("testTopic1", 0),
        TopicPartition("testTopic2", 0),
    ]
    init_consumer._set_topics(topic_partitions, [])

    init_consumer.consumer.assign.assert_called_once_with(topic_partitions)


def test_set_topics_exception(init_consumer, mocker):
    mocker.patch.object(init_consumer.consumer, "assign", side_effect=Exception)
    topic_partitions = [
        TopicPartition("testTopic1", 0),
        TopicPartition("testTopic2", 0),
    ]

    with pytest.raises(Exception):
        init_consumer._set_topics(topic_partitions, [])


def test_commit(init_consumer, kafka_messages, mocker, caplog):
    init_consumer._commit(kafka_messages)
    init_consumer.consumer.commit.assert_called_once

    mocker.patch.object(
        init_consumer.consumer, "commit", side_effect=Exception("wrong")
    )
    init_consumer._commit(kafka_messages)
    assert "Cannot commit message" in caplog.text


def test_dlq_path_uses_security_options(
        consumer_config_dict_with_sec_options,
        init_first_consumer,
        kafka_messages,
        mocker
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))

    producer_mock = mocker.patch(PRODUCER)

    dlq_topic_name = 'foo-dlq'
    consumer_config_dict_with_sec_options["dead_letter_queue_topic"] = dlq_topic_name

    KConsumer(consumer_config_dict_with_sec_options)

    dlq_producer_name = f'{consumer_config_dict_with_sec_options["name"]}-dlq'

    producer_mock.assert_called_once_with({
        "name": dlq_producer_name,
        "topics": [{"name": dlq_topic_name}],
        "bootstrap_servers": consumer_config_dict_with_sec_options["bootstrap_servers"],
        "ssl_ca_location": consumer_config_dict_with_sec_options["ssl_ca_location"],
        "ssl_certificate_location": consumer_config_dict_with_sec_options["ssl_certificate_location"],
        "ssl_key_location": consumer_config_dict_with_sec_options["ssl_key_location"],
    })


def test_filter_exception_causes_post_to_dlq_if_dlq_enabled(
        config_dict,
        init_first_consumer,
        kafka_messages,
        mocker
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = f'{test_consumer_conf["name"]}-dlq'

    c = init_first_consumer(config_dict)

    mocker.patch.object(c, "_msg_filter", side_effect=Exception)

    m = mocker.Mock()
    m.attach_mock(c._dlq_producer.send, "send")

    c._process_messages([kafka_messages])

    assert m.send.call_count == 1


def test_filter_exception_does_not_post_to_dlq_if_dlq_disabled(
        config_dict,
        init_first_consumer,
        kafka_messages,
        mocker
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = None

    c = init_first_consumer(config_dict)

    mocker.patch.object(c, "_msg_filter", side_effect=Exception)

    c._process_messages([kafka_messages])

    assert c._dlq_producer is None


def test_handler_exception_causes_post_to_dlq_if_dlq_enabled(
        config_dict,
        init_first_consumer,
        kafka_messages,
        mocker
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = f'{test_consumer_conf["name"]}-dlq'

    c = init_first_consumer(config_dict)

    mocker.patch.object(c, "_msg_filter", return_value=True)

    def raise_ex():
        raise Exception

    c._msg_handlers = [raise_ex]

    m = mocker.Mock()
    m.attach_mock(c._dlq_producer.send, "send")

    c._process_messages([kafka_messages])

    assert m.send.call_count == 1


def test_handler_exception_does_not_post_to_dlq_if_dlq_disabled(
        config_dict,
        init_first_consumer,
        kafka_messages,
        mocker
):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = None

    c = init_first_consumer(config_dict)

    mocker.patch.object(c, "_msg_filter", return_value=True)

    def raise_ex():
        raise Exception

    c._msg_handlers = [raise_ex]

    c._process_messages([kafka_messages])

    assert c._dlq_producer is None


def test_filter_exception_executes_commit_but_not_handlers(init_consumer, consumer_mocker, kafka_messages, caplog):
    mock_manager = consumer_mocker(filter_raise_ex=True)

    init_consumer._process_messages([kafka_messages])
    assert "Exception thrown from filter" in caplog.text
    # make sure commit is called
    mock_manager.mock_commit.assert_called()
    # handlers are not called
    assert not init_consumer._msg_handlers[0].handle_messages.called
    # commit is called after filter_message
    mock_manager.assert_has_calls([call.mock_filter_message(kafka_messages), call.mock_commit(kafka_messages)])


def test_filter_false_executes_commit_but_not_handlers(init_consumer, consumer_mocker, kafka_messages, caplog):
    mock_manager = consumer_mocker(filter_returns_false=True)

    init_consumer._process_messages([kafka_messages])
    # make sure commit is called
    mock_manager.mock_commit.assert_called()
    # handlers should be not be called
    assert not init_consumer._msg_handlers[0].handle_messages.called
    # commit is called after filter_message return false
    mock_manager.assert_has_calls([call.mock_filter_message(kafka_messages), call.mock_commit(kafka_messages)])


def test_handler_exception_executes_commit_after_handler(init_consumer, consumer_mocker, kafka_messages, caplog):
    mock_manager = consumer_mocker(handler_raise_ex=True)

    init_consumer._process_messages([kafka_messages])
    assert "Exception thrown from handler" in caplog.text

    # Commit is called after handle_message call
    mock_manager.assert_has_calls([call.mock_handle_messages(kafka_messages), call.mock_commit(kafka_messages)])


def test_commit_is_called_after_handler(init_consumer, consumer_mocker, kafka_messages, caplog):
    mock_manager = consumer_mocker()
    init_consumer._process_messages([kafka_messages])
    # Commit is called after handle_message call
    mock_manager.assert_has_calls([call.mock_handle_messages(kafka_messages), call.mock_commit(kafka_messages)])


def test_every_handler_attempted_before_commit(init_consumer, consumer_mocker, kafka_messages, caplog):
    mock_manager = consumer_mocker(handler_confs=[
        HandlerConf(handler_instance=MessageHandler1(), mock_name="handler0", raise_exception=False),
        HandlerConf(handler_instance=MessageHandler1(), mock_name="handler1", raise_exception=True),
        HandlerConf(handler_instance=MessageHandler1(), mock_name="handler2", raise_exception=False),
    ])
    init_consumer._process_messages([kafka_messages])

    mock_manager.assert_has_calls([
        call.handler0(kafka_messages),
        call.handler1(kafka_messages),
        call.handler2(kafka_messages),
        call.mock_commit(kafka_messages),
    ])


def test_commit_is_called_if_message_deserialization_throws_exception(
        init_consumer, consumer_mocker, kafka_messages, caplog):

    mock_manager = consumer_mocker(message_value_deserialization_raises_ex=True)
    init_consumer._process_messages([kafka_messages])
    assert "Exception thrown during message deserialization" in caplog.text
    assert mock_manager.mock_commit.called
    assert not mock_manager.mock_handle_messages.called


def test_message_value_deserialization_exception_uses_dlq_path(
        init_first_consumer, config_dict, consumer_mocker, mocker, kafka_messages, caplog):

    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = f'{test_consumer_conf["name"]}-dlq'

    c = init_first_consumer(config_dict)

    mock_manager = consumer_mocker(c, message_value_deserialization_raises_ex=True)

    m = mocker.Mock()
    m.attach_mock(c._dlq_producer.send, "send")

    c._process_messages([kafka_messages])

    assert "Exception thrown during message deserialization" in caplog.text
    assert mock_manager.mock_commit.called
    assert not mock_manager.mock_handle_messages.called
    assert m.send.call_count == 1


def test_message_key_deserialization_exception_uses_dlq_path(
        init_first_consumer, config_dict, consumer_mocker, mocker, kafka_messages, caplog):

    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = f'{test_consumer_conf["name"]}-dlq'

    c = init_first_consumer(config_dict)

    mock_manager = consumer_mocker(c, message_key_deserialization_raises_ex=True)

    m = mocker.Mock()
    m.attach_mock(c._dlq_producer.send, "send")

    c._process_messages([kafka_messages])

    assert "Exception thrown during message deserialization" in caplog.text
    assert mock_manager.mock_commit.called
    assert not mock_manager.mock_handle_messages.called
    assert m.send.call_count == 1


def test_every_handler_is_called_but_only_one_dlq_message_is_sent(
        config_dict, init_first_consumer, mocker, consumer_mocker, kafka_messages, caplog):

    test_consumer_conf = config_dict["kafka"].get("consumers")[0]
    test_consumer_conf["dead_letter_queue_topic"] = f'{test_consumer_conf["name"]}-dlq'

    c = init_first_consumer(config_dict)

    mock_manager = consumer_mocker(
        consumer=c,
        handler_confs=[
            HandlerConf(handler_instance=MessageHandler1(), mock_name="handler0", raise_exception=True),
            HandlerConf(handler_instance=MessageHandler1(), mock_name="handler1", raise_exception=True),
            HandlerConf(handler_instance=MessageHandler1(), mock_name="handler2", raise_exception=True),
        ]
    )

    m = mocker.Mock()
    m.attach_mock(c._dlq_producer.send, "send")

    c._process_messages([kafka_messages])

    mock_manager.assert_has_calls([
        call.handler0(kafka_messages),
        call.handler1(kafka_messages),
        call.handler2(kafka_messages),
        call.mock_commit(kafka_messages),
    ])
    assert m.send.call_count == 1


def test_register_filter(init_consumer):
    msg_filter = MessageFilter()

    init_consumer.register_filter(msg_filter)
    assert init_consumer._msg_filter == msg_filter

    with pytest.raises(ValueError, match=r"msg filter.* subclass of AbcMessageFilter"):
        init_consumer.register_filter(MessageHandler1())

    with pytest.raises(ValueError, match=r"msg filter has already been registered"):
        init_consumer.register_filter(msg_filter)


def test_register_handlers(init_consumer):
    msg_handlers = [MessageHandler1()]

    init_consumer.register_handlers(msg_handlers)
    assert init_consumer._msg_handlers == msg_handlers

    with pytest.raises(
        ValueError, match=r"msg handler.* subclass of AbcMessageHandler"
    ):
        init_consumer.register_handlers([MessageFilter()])


def test_process_message(init_consumer, mocker, kafka_messages):
    msg_filter = MessageFilter()
    msg_handlers = [MessageHandler1()]

    mocker.patch(COMMIT)

    init_consumer.register_filter(msg_filter)
    init_consumer.register_handlers(msg_handlers)
    init_consumer._process_messages([kafka_messages])
    # todo: (mpc) assertions


def test_process_message_filter_exception(
    init_consumer, mocker, kafka_messages, caplog
):
    msg_filter = MessageFilter()
    msg_handlers = [MessageHandler1()]

    mocker.patch(COMMIT)
    mocker.patch(GET_OFFSET, return_value=(0, 12))

    init_consumer.register_filter(msg_filter)
    init_consumer.register_handlers(msg_handlers)
    mocker.patch.object(init_consumer, "_msg_filter", side_effect=Exception)

    init_consumer._process_messages([kafka_messages])

    assert "Exception thrown from filter" in caplog.text
    init_consumer.consumer.commit.assert_called()


def test_process_message_handler_exception(
    init_consumer, mocker, kafka_messages, caplog
):
    msg_filter = MessageFilter()
    msg_handlers = [MessageHandler4(), MessageHandler3()]

    mocker.patch(COMMIT)
    mocker.patch(GET_OFFSET, return_value=(0, 12))

    init_consumer.register_filter(msg_filter)
    init_consumer.register_handlers(msg_handlers)

    init_consumer._process_messages([kafka_messages])
    assert "Exception thrown from handler" in caplog.text
    init_consumer.consumer.commit.assert_called()


def test_stop(init_consumer):
    init_consumer.stop()
    assert False == init_consumer.enabled


def test_close(init_consumer, mocker, caplog):
    mocker.patch.object(init_consumer.consumer, "unsubscribe")
    mocker.patch.object(init_consumer.consumer, "close")
    caplog.set_level(logging.INFO)

    init_consumer._close()

    init_consumer.consumer.close.assert_called_once_with()
    init_consumer.consumer.unsubscribe.assert_called_once_with()
    assert "Unsubscribed KafkaConsumer" in caplog.text
    assert "Closed KafkaConsumer" in caplog.text


def test_no_client_id(config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    config_dict["kafka"].get("consumers")[0]["client_id"] = None
    with pytest.raises(ValueError, match="Value of key: client_id not found"):
        # Init. Kconsumer without client_id
        KConsumer(config_dict["kafka"].get("consumers")[0])


def test_no_name(config_dict):
    config_dict["kafka"].get("consumers")[0]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    config_dict["kafka"].get("consumers")[0]["name"] = None
    with pytest.raises(ValueError, match="Value of key: name not found"):
        # Init. Kconsumer without name
        KConsumer(config_dict["kafka"].get("consumers")[0])


def test_start_exception(init_consumer, caplog):
    msg_filter = MessageFilter()

    with pytest.raises(ValueError, match=r"Message filter is missing*"):
        init_consumer.start()

    init_consumer.register_filter(msg_filter)
    with pytest.raises(ValueError, match=r"Message handler is missing*"):
        init_consumer.start()

    caplog.set_level(logging.INFO)
    init_consumer.started = True
    init_consumer.start()
    assert "already started in thread" in caplog.text

    init_consumer.started = False
    init_consumer.enabled = False
    init_consumer.start()
    assert "Consumer is not enabled" in caplog.text


def test_start(init_consumer):
    init_consumer.register_filter(MessageFilter())
    init_consumer.register_handlers([MessageHandler1()])
    init_consumer.start()
    assert init_consumer.started == True


def test_append_to_group_id(init_consumer):
    init_consumer.append_to_group_id("12")
    assert init_consumer._group_id == "mr-be-gr-2-12"

    init_consumer._group_id = None
    init_consumer.append_to_group_id("12")
    assert init_consumer._group_id == "12"

    init_consumer.started = True
    with pytest.raises(
        ValueError, match="Cannot append id to group_id of a running consumer"
    ):
        init_consumer.append_to_group_id("12")


def test_append_to_client_id(init_consumer):
    init_consumer.append_to_client_id("12")
    assert init_consumer._client_id == "mr_be_2-12"

    init_consumer._client_id = None
    init_consumer.append_to_client_id("12")
    assert init_consumer._client_id == "12"

    init_consumer.started = True
    with pytest.raises(
        ValueError, match="Cannot append id to client_id of a running consumer"
    ):
        init_consumer.append_to_client_id("12")


def test_pattern_config(config_dict, mocker):
    config_dict["kafka"].get("consumers")[3]["bootstrap_servers"] = config_dict[
        "kafka"
    ].get("bootstrap_servers")
    mocker.patch(CONSUMER)

    # normal config
    kconsumer = KConsumer(config_dict["kafka"].get("consumers")[3])
    kconsumer._init_consumer()
    mocker.patch.object(kconsumer.consumer, "subscribe")
    kconsumer._set_topics(*kconsumer._get_topics())

    kconsumer.consumer.subscribe.assert_called_once_with(
        topics=[config_dict["kafka"].get("consumers")[3].get("pattern")]
    )

    # Both topics and pattern are defined
    config_dict["kafka"].get("consumers")[3]["topics"] = ["topic"]
    with pytest.raises(ValueError, match=r"Cannot define both topics and pattern.*"):
        KConsumer(config_dict["kafka"].get("consumers")[3])

    # Pattern string doesn't start with '^'
    config_dict["kafka"].get("consumers")[3]["pattern"] = "t.*Topic?"
    escaped_pattern = re.escape("Pattern string doesn't start with '^': t.*Topic?")
    with pytest.raises(ValueError, match=escaped_pattern):
        KConsumer(config_dict["kafka"].get("consumers")[3])

    # Both topics and pattern are missing
    config_dict["kafka"].get("consumers")[3].pop("pattern")
    config_dict["kafka"].get("consumers")[3].pop("topics")
    with pytest.raises(
        ValueError, match=r"Either topics or pattern needs to be defined.*"
    ):
        KConsumer(config_dict["kafka"].get("consumers")[3])

    # Using regex on topic in allowed
    config_dict["kafka"].get("consumers")[3]["topics"] = [{"name": "^t.*Topic?"}]
    kconsumer = KConsumer(config_dict["kafka"].get("consumers")[3])
    kconsumer._init_consumer()
    mocker.patch.object(kconsumer.consumer, "subscribe")
    kconsumer._set_topics(*kconsumer._get_topics())


def test_get_messages(init_consumer, job_manager, mocker):
    constant.JOB_MANAGER = job_manager
    # max_parallel_job = 3 from config
    mocker.patch(GET_ACTIVE_JOB_COUNT, return_value=4)
    init_consumer._get_messages()
    assert init_consumer.pause.call_count == 1

    # Return empty list consumer is paused
    assert init_consumer._get_messages() == []

    mocker.patch(GET_ACTIVE_JOB_COUNT, return_value=2)
    init_consumer._get_messages()

    assert init_consumer.resume.call_count == 1


def test_get_topic_partition_offsets(init_consumer, mocker):
    mocker.patch(GET_OFFSET, return_value=(0, 12))
    assert (0, 12) == init_consumer.get_topic_partition_offsets("testTopic", 1)


def test_get_assignment(init_consumer, mocker):
    mocker.patch.object(
        init_consumer.consumer,
        "assignment",
        return_value=[TopicPartition("testTopic", 1)],
    )
    assignment = init_consumer.get_assignment()
    assert assignment == [TopicPartition("testTopic", 1)]

    mocker.patch.object(
        init_consumer.consumer, "assignment", side_effect=RuntimeError("Kafka error")
    )
    with pytest.raises(
        RuntimeError, match="Failed to get assignment for consumer consumer1"
    ):
        init_consumer.get_assignment()
