################################################################################
# Copyright (c) 2020-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
    producer.py
    -------------
    This module contains the KProducer class that creates a KafkaProducer instance based
    on yaml configuration, connect to Kafka server, and post messages to a list of topics
    defined in configuration file.
"""

import os
import sys
import json
import logging
import datetime
import secrets
from typing import Union
from collections import OrderedDict
from confluent_kafka import Producer
from confluent_kafka import KafkaError
from confluent_kafka import KafkaException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from drpbase import constant
from drpbase.utils import Utils
from prometheus_client import Gauge

KAFKA_PRODUCER_EXCEPTION = Gauge(
    "kafka_producer_exception",
    "Exception thrown by producer",
    ["c_name", "namespace", "producer"],
)


class KProducer:
    """Kafka producer wrapper class to post messages to a Kafka topic.
    Usage: Create KProducer object and call send(). Keep it around for reuse.
    The producer is thread safe and sharing a single producer instance across threads will
    generally be faster than having multiple instances.
    """

    ISO_FORMAT = "%Y-%m-%dT%I:%M:%S.%fZ"

    def __init__(self, producer_cfg):
        """
        Create a new KProducer instance based on configuration
        """

        self.logger = logging.getLogger(constant.LOGGER_NAME)

        # make sure configuration of producer exist
        if producer_cfg is None:
            self.logger.error(
                "Tried to create KProducer without supplying configuration."
            )
            raise ValueError(
                "Tried to create KProducer without supplying configuration."
            )

        self._producer_cfg = {}

        # Get bootstrap server from producer config.
        self._bootstrap_servers = Utils.get_config_value(
            producer_cfg, "bootstrap_servers", is_required=True, is_list=True
        )
        # Get topics from config if available
        self._topics = Utils.get_config_value(producer_cfg, "topics", is_list=True)

        self._value_serializer = lambda v: v.encode("utf-8")

        self._key = producer_cfg.get("key", None)
        self._key_serializer = lambda k: k.encode("utf-8")

        # The maximum number of unacknowledged requests that the producer will send
        # to the Kafka cluster before waiting for acknowledgments.
        # Default: 5, per Confluent kafka documentation.
        self._max_in_flight_reqs_per_conn = producer_cfg.get(
            "max_in_flight_reqs_per_conn", 5
        )

        # The maximum number of times the producer will retry sending a message to
        # the Kafka cluster before giving up.
        # Default: 2147483647, per Confluent kafka producer documentation.
        # Set default to 0 for KProducer.
        self._retries = producer_cfg.get("retries", 0)

        # The number of acknowledgments the producer requires the leader to have received
        # before considering a request complete.
        # Defaults to acks=1 if unset, per python kafka producer documentation.
        self._acks = producer_cfg.get("acks", 1)

        self.name = producer_cfg.get("name")
        self._message_type = producer_cfg.get("message_type", None)
        # do_flush flag to makes message immediately available to send. default: True
        self._do_flush = producer_cfg.get("do_flush", True)

        # Number of secs for polling timeout
        self._producer_timeout = constant.SIGNAL_HANDLER_WAIT_TIME

        self.producer = None
        self._producer_cfg["bootstrap.servers"] = ",".join(self._bootstrap_servers)
        self._producer_cfg["max.in.flight.requests.per.connection"] = (
            self._max_in_flight_reqs_per_conn
        )
        self._producer_cfg["retries"] = self._retries
        self._producer_cfg["acks"] = self._acks
        self._producer_cfg["on_delivery"] = self._delivery_report

        # Kafka brokers requiring authentication listen on 9093 port
        if "9093" in self._producer_cfg["bootstrap.servers"]:
            if "9092" in self._producer_cfg["bootstrap.servers"]:
                raise ValueError(
                    "Both non-ssl port 9092 and ssl port 9093 is found, which is not allowed"
                )
            self._producer_cfg["security.protocol"] = "SSL"

            self._ssl_ca_location = Utils.get_config_value(
                producer_cfg,
                "ssl_ca_location",
                default="/etc/secrets/kafka_dellca2018-bundle.crt",
            )
            self._ssl_certificate_location = Utils.get_config_value(
                producer_cfg,
                "ssl_certificate_location",
                default="/etc/secrets/kafka_certificate.pem",
            )
            self._ssl_key_location = Utils.get_config_value(
                producer_cfg,
                "ssl_key_location",
                default="/etc/secrets/kafka_private_key.pem",
            )

            self._producer_cfg["ssl.ca.location"] = self._ssl_ca_location
            self._producer_cfg["ssl.certificate.location"] = (
                self._ssl_certificate_location
            )
            self._producer_cfg["ssl.key.location"] = self._ssl_key_location

        self._validated_topics = OrderedDict()
        self._max_validated_topics_items = 100

        # initiate Kafka producer
        self._open()
        # make sure topic and partition exist on server
        if self._topics:
            self._validate_topic_partition(self._topics)

        self.c_name = os.getenv("CONTAINER_NAME", "NA")
        self.ns = os.getenv("DEPLOYMENT_NAMESPACE", "NA")

    @staticmethod
    def _get_uuid():
        """
            Generate a uuid string
        Returns:
            str: uuid string
        """
        s = str(secrets.token_hex(16))
        return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"

    @staticmethod
    def _zulu_timestamp():
        return datetime.datetime.utcnow().strftime(KProducer.ISO_FORMAT)

    def close(self):
        if self.producer is not None:
            try:
                self.flush()
                # Poll for any remaining delivery reports
                self.producer.poll(0)
            except Exception as ex:
                self.logger.error(
                    "Cannot close producer: %s: Exception type: %s, Message: %s",
                    self.name,
                    ex.__class__.__name__,
                    str(ex),
                )
            self.producer = None

    @Utils.attempt()
    def _open(self):
        if self.producer is None:
            try:
                self.producer = Producer(self._producer_cfg)
                # Producer() is an asynchronous producer. Call list_topics() to check server availability.
                # Increase timeout to 20 secs to avoid timeout error due to slow server response.
                self.producer.list_topics(timeout=constant.KAFKA_VALIDATION_TIMEOUT)
            except KafkaException as ex:
                self.logger.error(
                    "Failed to create KafkaProducer with brokers %s: Exception type: %s, Message: %s",
                    self._bootstrap_servers,
                    ex.__class__.__name__,
                    str(ex),
                )
                if ex.args[0].code() == KafkaError._TRANSPORT:
                    raise ValueError("NoBrokersAvailable") from ex

                raise

    @Utils.exception_handler
    def _get_payload(self, payload: object) -> dict:
        """
            Convert payload to dictionary if it is json
        Args:
            payload (object): a payload to be sent to Kafka server

        Raises:
            JSONDecodeError: if payload is not a valid json or dict

        Returns:
            dict: payload as dictionary
        """
        if isinstance(payload, dict):
            return payload

        # Attempt to convert payload to dictionary from json
        return json.loads(payload)

    def send(
        self, payload: object, topics: list[str] = None, msg_key: str = None
    ) -> Union[str, None]:
        """
            Send payload to Kafka server
        Args:
            payload (object): payload to be sent to Kafka server
            topics (list[str], optional): list of additional topics. Defaults to None.
            topic format: {'name': topic_name} or {'name': topic_name, 'partition': partition_num}
            msg_key (str, optional): Optional message key for this message. Defaults to None.

        Returns:
            Union[str, None]: uuid of message or None if exception
        """
        # If a key is passed in, it will overwrite the key defined in configuration.
        msg_key = self._key if msg_key is None else msg_key
        # Serialize key if it is not None
        msg_key = self._key_serializer(msg_key) if msg_key is not None else msg_key

        data = {}

        # Set values for the following required fields
        data["timestamp"] = self._zulu_timestamp()
        data["uuid"] = self._get_uuid()

        if self._message_type is not None:
            data["message_type"] = self._message_type

        kafka_payload = None
        try:
            if not topics:
                topics = []
            else:
                # make sure topic and partition exist on server
                self._validate_topic_partition(topics)

            payload = self._get_payload(payload)
            for key in payload.keys():
                data[key] = payload[key]

            kafka_payload = json.dumps(data)

            # Append topics from config to this topic list
            if self._topics:
                topics.extend(self._topics)

            if not topics:
                raise ValueError(f"No topic is defined for message {kafka_payload}")

            # Same message can be written to multiple topics
            for topic in topics:
                topic_name = topic.get("name")

                partition = topic.get("partition", None)
                # send message to Kafka server
                if partition:
                    self.producer.produce(
                        topic=topic_name,
                        key=msg_key,
                        value=self._value_serializer(kafka_payload),
                        partition=partition,
                    )
                else:
                    self.producer.produce(
                        topic=topic_name,
                        key=msg_key,
                        value=self._value_serializer(kafka_payload),
                    )

                # flush as default
                if self._do_flush:
                    self.producer.flush()

                KAFKA_PRODUCER_EXCEPTION.labels(self.c_name, self.ns, self.name).set(
                    0.0
                )

            return data["uuid"]
        except Exception as ex:
            self.logger.error(
                "Failed to send payload: %s, Exception type: %s, Message: %s",
                payload,
                ex.__class__.__name__,
                ex,
            )
            self.logger.error(
                "Please verify a topic is defined and it exists on server"
            )
            KAFKA_PRODUCER_EXCEPTION.labels(self.c_name, self.ns, self.name).inc()
            return None

    def _validate_topic_partition(self, topics):
        """
            validate all the topics exist on Kafka server
        Args:
            topics (list): a list of topics

        Raises:
            ValueError: Topic must have a name
            ValueError: Topic partition doesn't exist
        """
        for topic in topics:
            topic_name = topic.get("name", None)
            # if topic name isn't defined or empty, raise exception
            if topic_name is None or topic_name == "":
                raise ValueError("Topic must have a name.")

            # If a topic has been validated before and is in the buffer,
            # don't validate it again
            if self._validated_topics.get(topic_name, False):
                continue

            max_partition_number = self._get_max_partition_number(topic_name)

            partition = topic.get("partition", None)
            # if the partition defined in configuration is bigger than the biggest partition in server, raise exception
            if partition is not None:
                if partition >= max_partition_number:
                    raise ValueError(
                        f"Topic: {topic_name} partition: {partition} doesn't exist"
                    )

            self._validated_topics[topic_name] = True
            # remove the first one when buffer is full
            if len(self._validated_topics) > self._max_validated_topics_items:
                self.logger.warning(
                    "More than {self._max_validated_topics_items} topics are used."
                )
                self._validated_topics.popitem(last=False)

    def _get_max_partition_number(self, topic_name):
        """
            Get the maximum partition number for a topic
        Args:
            topic_name (str): topic name

        Raises:
            ValueError: Topic doesn't exist

        Returns:
            int: the maximum partition number
        """
        try:
            # Get topic metadata and then get topic partitions list from metadata
            topic_metadata = self.producer.list_topics(
                topic=topic_name, timeout=self._producer_timeout
            ).topics.get(topic_name)

            if topic_metadata.error is not None:
                if topic_metadata.error.code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    raise ValueError(f"Topic: {topic_name} doesn't exist")

            topic_partitions = topic_metadata.partitions

            # Get the number of partitions for the desired topic
            max_partition_number = len(topic_partitions)
            return max_partition_number
        except Exception as ex:
            self.logger.error(
                f"Error while checking for Topic: {topic_name}."
                + f" Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )
            raise

    def _delivery_report(self, err, message):
        """
            Delivery report callback to call (from poll() or flush()) on successful or failed delivery
        Args:
            err (KafkaError): A Kafka error
            message (Message): A Kafka message
        """
        if err is not None:
            self.logger.error(
                f"Error: {message.error()}. Message delivery failed: {message.value()}"
            )

        self.logger.debug(
            f"Topic: {message.topic()} Partition: {message.partition()} "
            + f"Offset: {message.offset()} Message: {message.value()}"
        )

    def flush(self, timeout: float = 0.0) -> int:
        """
            Wait for all messages in the Producer queue to be delivered.
        Args:
            timeout (float, optional): The maximum period of time in seconds to wait. Defaults to 0.0.
        Returns:
            int: The number of messages still in the queue
        """
        return self.producer.flush(timeout=timeout)
