#!/usr/bin/env python3
################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import sys
import pytest
import yaml

from confluent_kafka import Message

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from drpbase.helper import Helper
from drpbase import constant

GET_MESSAGES = "drpbase.helper.Helper._get_messages"
GET_OFFSET = "drpbase.helper.Helper._get_watermark_offsets"
TEST_DATA = "test data"


@pytest.fixture
def config_dict():
    constant.MAX_ATTEMPTS = 1
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    constant.SIGNAL_HANDLER_WAIT_TIME = 1
    return cfg


def kafka_messages(mocker, start=0, end=2):
    messages = []
    for i in range(start, end):
        a_message = mocker.Mock(spec=Message)
        a_message.error.return_value = None
        a_message.topic.return_value = "testTopic" + str(i)
        a_message.partition.return_value = i
        a_message.offset.return_value = i
        a_message.value.return_value = str.encode(TEST_DATA + str(i))

        messages.append(a_message)

    return messages


def test_no_bootstrap_server(config_dict):
    config_dict["last_message_retriever"]["bootstrap_servers"] = None
    with pytest.raises(ValueError, match="Value of key: bootstrap_servers not found"):
        Helper.get_last_kafka_messages(config_dict["last_message_retriever"])


def test_wrong_bootstrap_server(config_dict):
    with pytest.raises(Exception):
        Helper.get_last_kafka_messages(config_dict["last_message_retriever"])


def test_no_topics(config_dict):
    config_dict["last_message_retriever"]["topics"][0] = ""
    with pytest.raises(
        ValueError, match="Value of key: topics cannot contain empty value in List"
    ):
        Helper.get_last_kafka_messages(config_dict["last_message_retriever"])


def test_get_last_kafka_message_for_topic(mocker, config_dict):
    mocker.patch("drpbase.helper.Consumer")
    mocker.patch(GET_OFFSET, side_effect=Exception)

    with pytest.raises(Exception):
        Helper.get_last_kafka_messages(config_dict["last_message_retriever"])

    (min_offset, max_offset) = (0, 5)
    mocker.patch(GET_OFFSET, side_effect=lambda x, y: (min_offset, max_offset))
    mocker.patch(
        GET_MESSAGES,
        return_value=kafka_messages(mocker, max_offset - 1, max_offset + 2),
    )
    last_messages = Helper.get_last_kafka_messages(
        config_dict["last_message_retriever"]
    )

    assert last_messages["testTopic2"]["message"] == TEST_DATA + str(max_offset - 1)
    assert last_messages["testTopic4"]["message"] == TEST_DATA + str(max_offset - 1)

    mocker.patch(GET_MESSAGES, return_value=[])
    last_messages = Helper.get_last_kafka_messages(
        config_dict["last_message_retriever"]
    )

    assert last_messages["testTopic2"]["message"] == ""
    assert last_messages["testTopic4"]["message"] == ""


# This will be used to build the mocked messages with kafka_messages().
# - The mocked function _get_message() will return mock_start_offset as the first offset.
# - Also used to mock _get_last_offset.
mock_start_offset = 5


@pytest.mark.parametrize(
    "get_offset, min_offset, last_offset, expected",
    [
        (
            4,
            0,
            mock_start_offset,
            TEST_DATA + str(mock_start_offset - 1),
        ),  # Test valid get offset
        (5, 0, mock_start_offset, "Failed to get message"),  # Test invalid offset
        (
            "latest",
            0,
            mock_start_offset,
            TEST_DATA + str(mock_start_offset - 1),
        ),  # Test valid use of "latest"
        ("latest", 0, 0, ""),  # Test when new topic is found
        ("latest", 5, 5, ""),  # Test when all messages are purged from topic
        (
            "Latest",
            0,
            mock_start_offset,
            TEST_DATA + str(mock_start_offset - 1),
        ),  # Test mixed use of "latest"
        (
            "bad string",
            0,
            mock_start_offset,
            "Failed to get message",
        ),  # Test invalid string
    ],
)
def test_get_kafka_message(
    get_offset, min_offset, last_offset, expected, mocker, config_dict, caplog
):
    """
    Test get_kafka_message functions.

    Assumption: We are mocking _get_message and assume that it will return messages starting
                at the offset we have requested.
    Parameters:
        get_offset (int/str): Integer or String of the desired offset.
        expected (str): The expected returned value from the message at offset(get_offset).
                        Also used as search string for returned error messages.
    """
    mocker.patch("drpbase.helper.Consumer")
    mocker.patch(GET_MESSAGES, side_effect=Exception)

    with pytest.raises(Exception):
        Helper.get_kafka_message(config_dict["last_message_retriever"], get_offset)

    mocker.patch(GET_OFFSET, side_effect=lambda x, y: (min_offset, last_offset))
    mocker.patch(
        GET_MESSAGES,
        return_value=kafka_messages(
            mocker, mock_start_offset - 1, mock_start_offset + 2
        ),
    )
    try:
        last_messages = Helper.get_kafka_message(
            config_dict["last_message_retriever"], get_offset
        )

        assert last_messages["testTopic2"]["message"] == expected
        assert last_messages["testTopic4"]["message"] == expected
    except AssertionError:
        raise
    except Exception:
        assert expected in caplog.text
