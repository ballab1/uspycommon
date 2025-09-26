#!/usr/bin/env python3
################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import pytest
import yaml

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from drpbase.consumers import KConsumers
from messages.mymessagefilter import MessageFilter
from messages.mymessagehandler import MessageHandler1, MessageHandler2

STOP = "isgkafka.consumer.KConsumer.stop"
START = "drpbase.consumers.KConsumer.start"


@pytest.fixture
def config_dict():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    return cfg


@pytest.fixture
def init_consumers(config_dict, mocker):
    mocker.patch(
        "drpbase.consumers.KConsumers._init_consumer", side_effect=lambda x: None
    )

    return KConsumers(config_dict["kafka"])


@pytest.fixture(name="consumers")
def fixture_consumers(config_dict, mocker):
    mocker.patch("isgkafka.consumer.Consumer")
    mocker.patch("drpbase.consumers.KConsumer._get_topics")
    mocker.patch("drpbase.consumers.KConsumer._set_topics")
    mocker.patch(START)
    mocker.patch(STOP)

    return KConsumers(config_dict["kafka"])


def test_get_msg_filter(init_consumers, config_dict):
    """
    A test function that test get_msg_filter method.
    """

    my_filter = init_consumers._get_msg_filter(config_dict["kafka"].get("consumers")[0])
    expected_return = "<class 'messages.mymessagefilter.MessageFilter'>"

    assert str(type(my_filter)) == expected_return

    # The third consumer doesn't have filter defined in configuration
    my_filter = init_consumers._get_msg_filter(config_dict["kafka"].get("consumers")[2])
    assert None is my_filter


def test_get_msg_handlers(init_consumers, config_dict):
    """
    A test function that test get_msg_handlers
    """

    handlers = init_consumers._get_msg_handlers(
        config_dict["kafka"].get("consumers")[1]
    )
    expected_return = {
        "<class 'messages.mymessagehandler.MessageHandler1'>",
        "<class 'messages.mymessagehandler.MessageHandler2'>",
        "<class 'messages.mymessagehandler2.MessageHandler3'>",
        "<class 'messages.mymessagehandler2.MessageHandler4'>",
    }
    handlers_return = set()
    assert type(handlers) is list
    assert len(handlers) == 4

    # Check if all message handler classes are found
    handlers_return.update(set([str(type(handle)) for handle in handlers]))
    assert expected_return == handlers_return

    # The third consumer doesn't have handlers defined in configuration
    handlers = init_consumers._get_msg_handlers(
        config_dict["kafka"].get("consumers")[2]
    )
    assert [] == handlers


def test_not_consumer():
    with pytest.raises(ValueError):
        # Test not consumer configuration
        KConsumers({"config": "None"})


def test_start_consumers(config_dict, mocker):
    mocker.patch("drpbase.consumers.KConsumer.__init__", side_effect=lambda x: None)
    mocked_kconsumer_get_msg_filter = mocker.patch(
        "drpbase.consumers.KConsumers._get_msg_filter"
    )
    msg_filter = MessageFilter()
    mocked_kconsumer_get_msg_filter.side_effect = [msg_filter, None, None]

    mocked_kconsumer_get_msg_handlers = mocker.patch(
        "drpbase.consumers.KConsumers._get_msg_handlers"
    )
    msg_handler1 = MessageHandler1()
    msg_handler2 = MessageHandler2()
    mocked_kconsumer_get_msg_handlers.side_effect = [
        [msg_handler1, msg_handler2],
        None,
        None,
    ]

    mocked_kconsumer_register_filter = mocker.patch(
        "drpbase.consumers.KConsumer.register_filter", return_value=None
    )
    mocked_kconsumer_register_handlers = mocker.patch(
        "drpbase.consumers.KConsumer.register_handlers", return_value=None
    )
    mocked_kconsumer_start = mocker.patch(START, return_value=None)

    consumers = KConsumers(config_dict["kafka"])

    # test message filter and handlers are registered and consumer starts
    mocked_kconsumer_register_filter.assert_called_with(msg_filter)
    mocked_kconsumer_register_handlers.assert_called_with([msg_handler1, msg_handler2])

    consumers.start_consumers()
    mocked_kconsumer_start.assert_called_with()

    # There are 3 consumers defined in the configuration. One is marked as disabled.
    # Make sure 2 consumers start.
    assert mocked_kconsumer_start.call_count == 3

    mocker.patch(START, side_effect=Exception)
    with pytest.raises(Exception, match=r"Cannot start consumers"):
        # Test exception when starting consumer
        consumers.start_consumers()

    # attempt to reuse same message filter on other consumer
    with pytest.raises(
        ValueError, match=r"This Object id: .* has already been registered.*"
    ):
        consumers.register_filter("consumer3", msg_filter)


def test_consumer_name(config_dict, mocker):
    mocker.patch("drpbase.consumers.KConsumer")

    # Test when creating consumer with empty name
    config_dict["kafka"].get("consumers")[0]["name"] = ""
    with pytest.raises(Exception, match=r"Cannot create a consumer"):
        KConsumers(config_dict["kafka"])

    # Test when creating consumers using the same consumer name
    config_dict["kafka"].get("consumers")[0]["name"] = "consumer1"
    config_dict["kafka"].get("consumers")[2]["name"] = "consumer1"
    with pytest.raises(Exception, match=r".*Cannot create a consumer"):
        KConsumers(config_dict["kafka"])


def test_create_consumer_exception(config_dict, mocker):
    mocker.patch(
        "drpbase.consumers.KConsumer.__init__", side_effect=Exception("mocked error")
    )
    with pytest.raises(Exception, match=r".*Cannot create a consumer"):
        # Test exception when creating consumer
        KConsumers(config_dict["kafka"]).start_consumers()


def test_stop_consumers(mocker, consumers):
    mocked_stop = mocker.patch(STOP)

    consumers.stop_consumers()
    mocked_stop.assert_called_with()


def test_stop_consumer(mocker, consumers):
    mocked_stop = mocker.patch(STOP)

    consumers.stop_consumer("consumer1")
    mocked_stop.assert_called_with()

    with pytest.raises(Exception, match=r"Consumer.* not found"):
        consumers.stop_consumer("wrong_name")

    consumers._consumers.clear()
    with pytest.raises(Exception, match=r"Consumer.* not found"):
        consumers.stop_consumer("consumer1")


def test_get_by_name(consumers):
    assert consumers.get_by_name("wrong_name") is None
    assert consumers.get_by_name("consumer1") is not None

    consumers._consumers.clear()
    assert consumers.get_by_name("consumer1") is None


def test_register_filter(consumers):
    my_filter = MessageFilter()
    consumers.register_filter("consumer3", my_filter)
    assert consumers.get_by_name("consumer3")._msg_filter == my_filter

    with pytest.raises(Exception, match=r"Consumer: .* not found"):
        consumers.register_filter("wrong_name", my_filter)


def test_register_handlers(consumers):
    handler = MessageHandler1()
    consumers.register_handlers("consumer3", [handler])
    assert consumers.get_by_name("consumer3")._msg_handlers == [handler]

    with pytest.raises(Exception, match=r"Consumer: .* not found"):
        consumers.register_handlers("wrong_name", filter)


def test_start_consumer(consumers, mocker):
    consumers.start_consumer("consumer1")
    consumers.get_by_name("consumer1").start.assert_called_with()

    mocker.patch.object(
        consumers.get_by_name("consumer1"), "start", side_effect=Exception
    )
    with pytest.raises(Exception, match="Cannot start a consumer"):
        consumers.start_consumer("consumer1")


def test_append_to_group_id(consumers):
    consumers.append_to_group_id("consumer3", "1234567890")
    assert consumers.get_by_name("consumer3")._group_id == "mr-be-gr-1-1234567890"

    with pytest.raises(Exception, match="Consumer: .* not found"):
        consumers.append_to_group_id("consumer2", "1234567890")


def test_append_to_client_id(consumers):
    consumers.append_to_client_id("consumer3", "1234567890")
    assert consumers.get_by_name("consumer3")._client_id == "mr_be_1-1234567890"

    with pytest.raises(Exception, match="Consumer: .* not found"):
        consumers.append_to_client_id("consumer2", "1234567890")
