################################################################################
# Copyright (c) 2022-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
import logging
from confluent_kafka import Consumer
from confluent_kafka import KafkaError
from confluent_kafka import KafkaException
from confluent_kafka import TopicPartition


from . import constant
from .utils import Utils

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

LATEST = "latest"


class Helper:
    """
    Helper class
    """

    @classmethod
    def get_kafka_message(cls, consumer_cfg, offset):
        """Get the message with the offset for each topic from partition 0 using Kafka consumer configuration

        Args:
            consumer_cfg (dict): A kafka configuration that contains the following minimum setting:
            1. bootstrap_servers
            2, A list of topics
            3. group_id
            offset (int/str): a integer of the topic offset to retrieve
                              string "latest" can be sent to retrieve last message

        Raises:
            ValueError: bootstrap_servers need to be a non-empty array
            ValueError: topics need to be a non-empty array

        Exception:  Failed to initialize kafka consumer using config
                    Failed to get messages

        Returns:
            dict of dict: key: topic name, Value: {'message': last message, 'offset': offset}
        """
        cls.logger = logging.getLogger(constant.LOGGER_NAME)
        offset_messages = {}

        bootstrap_servers = Utils.get_config_value(
            consumer_cfg, "bootstrap_servers", is_required=True, is_list=True
        )
        topics = Utils.get_config_value(
            consumer_cfg, "topics", is_required=True, is_list=True
        )
        group_id = Utils.get_config_value(consumer_cfg, "group_id", is_required=True)

        # Create a python KafkaConsumer config and initialize KafkaConsumer instance
        kafka_config = {}

        kafka_config["bootstrap.servers"] = ",".join(bootstrap_servers)
        kafka_config["group.id"] = group_id
        kafka_config.setdefault("enable.auto.commit", False)
        kafka_config.setdefault("auto.offset.reset", "earliest")
        kafka_config.setdefault("logger", cls.logger)

        if "9093" in ",".join(bootstrap_servers):
            if "9092" in ",".join(bootstrap_servers):
                raise ValueError(
                    "Both non-ssl port 9092 and ssl port 9093 is found, which is not allowed"
                )
            kafka_config["security.protocol"] = "SSL"
            kafka_config["ssl.ca.location"] = Utils.get_config_value(
                consumer_cfg,
                "ssl_ca_location",
                default="/etc/secrets/kafka_dellca2018-bundle.crt",
            )
            kafka_config["ssl.certificate.location"] = Utils.get_config_value(
                consumer_cfg,
                "ssl_certificate_location",
                default="/etc/secrets/kafka_certificate.pem",
            )
            kafka_config["ssl.key.location"] = Utils.get_config_value(
                consumer_cfg,
                "ssl_key_location",
                default="/etc/secrets/kafka_private_key.pem",
            )

        consumer = cls._init_consumer(kafka_config)

        try:
            topic_names = []
            for topic in topics:
                topic_name = topic.get("name", None)
                if topic_name and len(topic_name.strip()) != 0:
                    topic_names.append(topic_name.strip())

            for topic_name in topic_names:
                message = None
                message, retrieved_offset = cls._get_kafka_message(
                    topic_name, consumer, offset
                )
                offset_messages[topic_name] = {}

                if message:
                    offset_messages[topic_name]["message"] = message.value().decode(
                        "utf-8"
                    )
                else:
                    offset_messages[topic_name]["message"] = ""

                offset_messages[topic_name]["offset"] = retrieved_offset
        except Exception as ex:
            cls.logger.error(
                "Failed to get message. Exception type: %s, Exception Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise
        finally:
            consumer.unsubscribe()
            consumer.unassign()
            consumer.close()

        return offset_messages

    @classmethod
    def get_last_kafka_messages(cls, consumer_cfg):
        """Get the last message for each topic from partition 0 using Kafka consumer configuration

        Args:
            consumer_cfg (dict): A kafka configuration that contains the following minimum setting:
            1. bootstrap_servers
            2, A list of topics
            3. group_id

        Returns:
            dict of dict: key: topic name, Value: {'message': last message, 'offset': offset}
        """
        return cls.get_kafka_message(consumer_cfg, LATEST)

    @classmethod
    @Utils.attempt()
    def _init_consumer(cls, kafka_config):
        """
        Create a Confluent Kafka consumer instance and return it.
        Use attempt decorator to recover temporary connection lost to Kafka server.

        Args:
            kafka_config (dict): A kafka configuration

        Raises:
            KafkaException: Failed to initialize kafka consumer using config

        Returns:
            Consumer: a Confluent Kafka consumer instance
        """
        try:
            consumer = Consumer(kafka_config)
            # Call list_topics() to invoke asynchronous API and check server availability.
            consumer.list_topics(timeout=constant.SIGNAL_HANDLER_WAIT_TIME)
            return consumer
        except KafkaException as ex:
            cls.logger.error(
                "Failed to initialize kafka consumer using config. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise

    @classmethod
    def _get_watermark_offsets(cls, consumer, topic_partition):
        """Retrieve low and high offsets for the specified partition

        Args:
            consumer (Consumer): a Confluent Kafka consumer
            topic_partition (TopicPartition): a TopicPartition

        Raises:
            Exception: Failed to get offset

        Returns:
            tuple: min_offset, max_offset for input topic partition
        """
        try:
            # get the min and max offset for that TopicPartition
            min_offset, max_offset = consumer.get_watermark_offsets(
                topic_partition, timeout=constant.SIGNAL_HANDLER_WAIT_TIME
            )
            return min_offset, max_offset
        except Exception as ex:
            cls.logger.error(
                "Failed to get offset for topic_partition %s. Exception type: %s, Exception Message: %s",
                topic_partition,
                ex.__class__.__name__,
                str(ex),
            )
            raise

    @classmethod
    def _get_kafka_message(cls, topic_name, consumer, offset):
        """Get the Kafka message for input topic and offset

        Args:
            topic_name (str): a topic name
            consumer (Consumer): a Kafka consumer
            offset (int/str): integer offset to retrieve,
                              string "latest" can be sent to retrieve last message

        Raises:
            ValueError: Topic doesn't exist or offset is invalid
                        If offset is not an integer
            Exception: Failed to get last message on topic

        Returns:
            message (Kafka message), offset: None, if maximum offset = 0(for new topics), offset(-1)
            message (Kafka message), offset: the Kafka message on input topic, offset
        """
        try:
            current_message = None
            # create a TopicPartition object using topic name and partition 0
            tp = TopicPartition(topic_name, 0)

            # If topic doesn't exist in Kafka, an exception is raised.
            # Get topic metadata and then get topic partitions list from metadata
            topic_metadata = consumer.list_topics(
                topic=topic_name, timeout=constant.SIGNAL_HANDLER_WAIT_TIME
            ).topics.get(topic_name)

            if topic_metadata.error is not None:
                if topic_metadata.error.code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    msg = f"Topic: {topic_name} doesn't exist"
                    cls.logger.error(msg)
                    raise ValueError(msg)

            # get the min and max offsets for that TopicPartition
            min_offset, max_offset = cls._get_watermark_offsets(consumer, tp)

            # Check if the last message is wanted
            if isinstance(offset, str) and offset.lower() == LATEST:
                # If max_offset is 0, this is a new topic. So just return None as message
                # If min_offset and max_offset are the same, that means no message on topic.
                # Return None as message with the latest offset if that happens.
                if max_offset == 0 or min_offset == max_offset:
                    # return offset = -1 to indicate this is a new topic
                    return current_message, max_offset - 1
                # The high offset is the offset of the last message + 1.
                offset = max_offset - 1
            else:
                try:
                    offset = int(offset)
                except ValueError as ex:
                    cls.logger.error(
                        "Offset is not a integer. Exception type: %s, Exception Message: %s",
                        ex.__class__.__name__,
                        str(ex),
                    )
                    raise ValueError("Failed to get offset") from ex

            # Verify offset is valid
            if offset < min_offset or offset >= max_offset:
                msg = (
                    f"Offset: {offset} doesn't exist for {topic_name}. "
                    + f"Offset range: ({min_offset}, {max_offset-1})"
                )
                cls.logger.error(msg)
                raise ValueError(msg)

            # Assign offset to topic partition
            tp.offset = offset

            # assign consumer to that TopicPartition
            consumer.assign([tp])

            # Get the first message and break
            msgs = cls._get_messages(consumer)
            for message in msgs:
                cls.logger.debug(
                    f"Retrieved offset: {message.offset()} Message: {message.value()}"
                )
                current_message = message
                break

            return current_message, offset
        except Exception as ex:
            cls.logger.error(
                "Failed to get offset on topic %s. Exception type: %s, Exception Message: %s",
                topic_name,
                ex.__class__.__name__,
                str(ex),
            )
            raise

    @classmethod
    def _get_messages(cls, consumer):
        """Return a list of messages

        Args:
            consumer (KafkaConsumer): a Kafka consumer

        Returns:
            iterator: messages
        """
        return consumer.consume(timeout=constant.SIGNAL_HANDLER_WAIT_TIME)
