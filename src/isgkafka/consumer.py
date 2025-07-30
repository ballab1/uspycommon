################################################################################
# Copyright (c) 2020-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import sys
import json
import logging
import threading
import time
from typing import List

from confluent_kafka import Consumer
from confluent_kafka import KafkaError
from confluent_kafka import KafkaException
from confluent_kafka import Message as KafkaMessage
from confluent_kafka import TopicPartition
from confluent_kafka import OFFSET_STORED
from confluent_kafka import OFFSET_BEGINNING

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from drpbase import constant
from drpbase.utils import Utils
from isgkafka.producer import KProducer
from prometheus_client import Summary, Gauge

from .messagehandler import AbcMessageHandler
from .messagefilter import AbcMessageFilter


KAFKA_HANDLER_TIME = Summary(
    "kafka_handler_processing",
    "Time spent in handling a Kafka payload",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_FILTER_TIME = Summary(
    "kafka_filter_processing",
    "Time spent in filtering a Kafka payload",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_HANDLER_EXCEPTION = Gauge(
    "kafka_handler_exception",
    "Number of exceptions thrown by handler",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_FILTER_EXCEPTION = Gauge(
    "kafka_filter_exception",
    "Number of exceptions thrown by filter",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_CONSUMER_MIN_OFFSET = Gauge(
    "kafka_consumer_min_offset",
    "Min offset of the Consumer",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_CONSUMER_MAX_OFFSET = Gauge(
    "kafka_consumer_max_offset",
    "Max offset of the Consumer",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_CONSUMER_CURRENT_OFFSET = Gauge(
    "kafka_consumer_current_offset",
    "Current offset of the Consumer",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag",
    "Number of pending messages to be consumed",
    ["topic", "partition", "client_id", "group_id"],
)
KAFKA_CONSUMER_LAG_HIGH = Gauge(
    "kafka_consumer_lag_high",
    "Enabled when Consumer Lag is more than defined threshold",
    ["topic", "partition", "client_id", "group_id"],
)


class KConsumer:
    """
    KConsumer class
    """

    def __init__(self, consumer_cfg):
        """
        Create a new KConsumer based on consumer configuration
        param consumer_cfg: A dictionary that contains one consumer configuration
        """

        self.logger = logging.getLogger(constant.LOGGER_NAME)
        self.logger.info("Creating KConsumer")

        self.enabled = consumer_cfg.get("enabled", False)
        self.started = False
        self._is_authenticated = False

        # get settings from configuration file
        self._bootstrap_servers = Utils.get_config_value(
            consumer_cfg, "bootstrap_servers", is_required=True, is_list=True
        )
        self._topics = Utils.get_config_value(consumer_cfg, "topics", is_list=True)
        self._pattern = Utils.get_config_value(consumer_cfg, "pattern")
        if self._pattern and not self._pattern.startswith("^"):
            raise ValueError(f"Pattern string doesn't start with '^': {self._pattern}")

        self.name = Utils.get_config_value(consumer_cfg, "name", is_required=True)

        # Either topics or pattern needs be defined for one consumer, but not both.
        if self._topics is None and self._pattern is None:
            raise ValueError(
                f"Either topics or pattern needs to be defined for consumer {self.name}"
            )

        if self._topics and self._pattern:
            raise ValueError(
                f"Cannot define both topics and pattern for consumer {self.name}"
            )

        self._group_id = Utils.get_config_value(
            consumer_cfg, "group_id", is_required=True
        )
        self._client_id = Utils.get_config_value(
            consumer_cfg, "client_id", is_required=True
        )

        # Default: True, per Confluent kafka consumer documentation.
        self._enable_auto_commit = Utils.get_config_value(
            consumer_cfg, "enable_auto_commit", default=False
        )

        # Default: False. The flag is to indicate job manager is used in this consumer.
        self._throttle_max_running_jobs = Utils.get_config_value(
            consumer_cfg, "throttle_max_running_jobs", default=False
        )

        # Default: 10000, per Confluent kafka consumer documentation.
        self._session_timeout_ms = Utils.get_config_value(
            consumer_cfg, "session_timeout_ms", default=60000
        )

        # Default: 'latest', per Confluent kafka consumer documentation.
        self._auto_offset_reset = Utils.get_config_value(
            consumer_cfg, "auto_offset_reset", default="earliest"
        )
        if self._auto_offset_reset not in ("earliest", "latest"):
            raise ValueError("auto_offset_reset can only be either earliest or latest")

        # Consumer lag threshold to alert
        self._consumer_lag_threshold_to_alert = Utils.get_config_value(
            consumer_cfg,
            "consumer_lag_threshold_to_alert",
            default=constant.DEFAULT_CONSUMER_LAG_THRESHOLD_TO_ALERT,
        )

        # Number of secs for polling timeout
        self._consumer_timeout = constant.SIGNAL_HANDLER_WAIT_TIME

        self._ssl_ca_location = None
        self._ssl_certificate_location = None
        self._ssl_key_location = None

        # Kafka brokers requiring authentication listen on 9093 port
        if "9093" in ",".join(self._bootstrap_servers):
            if "9092" in ",".join(self._bootstrap_servers):
                raise ValueError(
                    "Both non-ssl port 9092 and ssl port 9093 is found, which is not allowed"
                )
            self._is_authenticated = True
            self._ssl_ca_location = Utils.get_config_value(
                consumer_cfg,
                "ssl_ca_location",
                default="/etc/secrets/kafka_dellca2018-bundle.crt",
            )
            self._ssl_certificate_location = Utils.get_config_value(
                consumer_cfg,
                "ssl_certificate_location",
                default="/etc/secrets/kafka_certificate.pem",
            )
            self._ssl_key_location = Utils.get_config_value(
                consumer_cfg,
                "ssl_key_location",
                default="/etc/secrets/kafka_private_key.pem",
            )

        self._dlq_producer = None  # type: KProducer | None
        self._dlq_topic = None  # type: str | None

        if dlq_topic := Utils.get_config_value(consumer_cfg, "dead_letter_queue_topic"):
            self._dlq_topic = dlq_topic
            self._dlq_producer = KProducer({
                "name": f"{self.name}-dlq",
                "topics": [{"name": self._dlq_topic}],
                "bootstrap_servers": self._bootstrap_servers,
                "ssl_ca_location": self._ssl_ca_location,
                "ssl_certificate_location": self._ssl_certificate_location,
                "ssl_key_location": self._ssl_key_location,
            })

        # message filter and handlers placeholders
        self._msg_filter = None
        self._msg_handlers = []

        self._thrd_name = None
        self.consumer = None

        self._paused = False

    @Utils.attempt()
    def _init_consumer(self):
        """
            Create KafkaConsumer instance using configuration
        Raises:
            ex: Failed to initialize kafka consumer using config
        """
        try:
            # Create a python KafkaConsumer config and initialize KafkaConsumer instance
            kafka_config = {}
            kafka_config["debug"] = "all"  # set debug to all to enable core dump
            kafka_config["group.id"] = self._group_id
            kafka_config["bootstrap.servers"] = ",".join(self._bootstrap_servers)
            kafka_config["client.id"] = self._client_id

            if self._is_authenticated:
                kafka_config["security.protocol"] = "SSL"
                kafka_config["ssl.ca.location"] = self._ssl_ca_location
                kafka_config["ssl.certificate.location"] = (
                    self._ssl_certificate_location
                )
                kafka_config["ssl.key.location"] = self._ssl_key_location

            kafka_config.setdefault("logger", self.logger)
            kafka_config.setdefault("session.timeout.ms", self._session_timeout_ms)
            kafka_config.setdefault("enable.auto.commit", self._enable_auto_commit)
            kafka_config.setdefault("auto.offset.reset", self._auto_offset_reset)

            # The frequency at which the consumer sends heartbeat requests to
            # the broker to keep the session alive.
            # Default: 3000 milliseconds per Confluent kafka consumer documentation.
            # Copied from current production implementation
            kafka_config.setdefault("heartbeat.interval.ms", 30000)

            # The maximum amount of time that can elapse between calls to the poll() method.
            # Default: 300,000 milliseconds per Confluent kafka consumer documentation.
            # Copied from current production implementation
            kafka_config.setdefault("max.poll.interval.ms", 3600000)

            self.logger.info("Kafka Brokers: %s", self._bootstrap_servers)
            self.logger.info("Consumer Name: %s", self.name)
            self.logger.info("Group ID: %s", self._group_id)
            self.logger.info("Client ID: %s", self._client_id)

            self.consumer = Consumer(kafka_config)
            # Call list_topics() to invoke asynchronous API and check server availability.
            # Increase timeout to 20 secs to avoid timeout error due to slow server response.
            self.consumer.list_topics(timeout=constant.KAFKA_VALIDATION_TIMEOUT)
        except KafkaException as ex:
            self.logger.error(
                "Failed to initialize kafka consumer using config. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            if ex.args[0].code() == KafkaError._TRANSPORT:
                raise ValueError("NoBrokersAvailable") from ex

            raise

    def register_filter(self, msg_filter):
        """Register a filter for this consumer. Only one filter is allowed.

        Args:
            msg_filter (AbcMessageFilter): an instance that implements AbcMessageFilter

        Raises:
            ValueError: A msg filter must be a subclass of AbcMessageFilter
            ValueError: msg filter has already been registered
        """
        self.logger.info("Registering message filter")

        # Only instance of class that implements AbcMessageFilter is allowed
        if isinstance(msg_filter, AbcMessageFilter) is False:
            raise ValueError("msg filter must be a subclass of AbcMessageFilter")

        if self._msg_filter is not None:
            raise ValueError("A msg filter has already been registered")

        self._msg_filter = msg_filter

    def register_handlers(self, msg_handlers: List[AbcMessageHandler]):
        """Register a list of handlers that implements AbcMessageHandler.

        Args:
            msg_handlers (List[AbcMessageHandler]):a list of instances that implement AbcMessageHandler

        Raises:
            ValueError: msg handler must be a subclass of AbcMessageHandler
        """
        self.logger.info("Registering message handlers")
        for msg_handler in msg_handlers:
            # Only instance of class that implements AbcMessageHandler is allowed
            if isinstance(msg_handler, AbcMessageHandler) is False:
                raise ValueError("msg handler must be a subclass of AbcMessageHandler")

            self._msg_handlers.append(msg_handler)

    def start(self):
        """Start consumer thread. Raise exception if filter or handlers are missing.

        Raises:
            ValueError: Message filter is missing. Consumer cannot start
            ValueError: Message handler is missing. Consumer cannot start.
        """
        if not self.started:
            if self.enabled:
                if self._msg_filter is None:
                    raise ValueError(
                        "Message filter is missing. Consumer cannot start."
                    )

                if not self._msg_handlers:
                    raise ValueError(
                        "Message handler is missing. Consumer cannot start."
                    )

                # lazy initialization of consumer and set topics
                self._init_consumer()

                # subscribe or assign topics
                self._set_topics(*self._get_topics())

                self._thrd_name = "kcon-cid-" + self._client_id
                thrd = threading.Thread(
                    target=self._consume_message, name=self._thrd_name
                )
                thrd.start()
                self.logger.info(
                    "Starting KafkaConsumer %s in thread %s",
                    self._client_id,
                    self._thrd_name,
                )
                self.started = True
            else:
                self.logger.info(
                    "Consumer is not enabled. Kafka consumer thread won't start."
                )
        else:
            self.logger.info(
                "Consumer: %s has already started in thread %s",
                self._client_id,
                self._thrd_name,
            )

    def _get_topics(self):
        """
            Get list of topic partitions and list of topic names.
        Raises:
            ValueError: Invalid topic configuration

        Returns:
            tuple: list of topic partitions and list of topic names
        """
        topic_partitions = []
        topic_names = set()

        # if there isn't topics defined in configuration, return empty
        if self._topics is None:
            return topic_partitions, topic_names

        for topic in self._topics:
            topic_name = topic.get("name", None)

            # if topic_name is a regexp pattern, add to list of topic names directly.
            # Regexp pattern subscriptions are only supported by prefixing the topic string with "^".
            if topic_name.startswith("^"):
                topic_names.add(topic_name)
                continue

            # get the largest partition number for a given topic.
            # if a partition requested in the configuration is bigger than
            # the max_partition_number, an exception will be raised.
            max_partition_number = self._get_max_partition_number(topic_name)

            # Add topics with partition/offset information to topic_partition dictionary or add names of topics without
            # partition/offset information to topic_name set. One of these two will be empty.
            # In one consumer, we don't support mix of topics with partition/offset and topics without partition/offset.
            # An exception will be raised if that happens.
            error_message = (
                f"ERROR: Invalid topic configuration: [{topic_name}]. A consumer"
                ' can be "subscribed" to multiple topics *or* be "assigned" to'
                " multiple specific partitions, but not both."
            )
            if "partitions" in topic and topic.get("partitions", None) is not None:
                if len(topic_names) > 0:
                    raise ValueError(error_message)

                self._get_topic_partitions(
                    topic_name,
                    topic.get("partitions"),
                    max_partition_number,
                    topic_partitions,
                )
            else:
                if len(topic_partitions) > 0:
                    raise ValueError(error_message)

                topic_names.add(topic_name)

        return topic_partitions, sorted(list(topic_names))

    def _get_topic_partitions(
        self, topic_name, partitions, max_partition_number, topic_partitions
    ):
        for partition in partitions:
            partition_number = int(partition.get("number"))

            # raise exception if requested partition is bigger than maximum partition available.
            if partition_number < max_partition_number:
                # If offset is defined in config, set it to -1 (OFFSET_END)
                offset = partition.get("offset", -1)
                topic_partition = TopicPartition(
                    topic=topic_name, partition=partition_number
                )

                # get the offset boundary
                min_offset, max_offset = self._get_watermark_offsets(
                    topic_partition, cached=False
                )

                # If offset is not set or is set to -1, move to the last committed offset
                if offset == -1:
                    topic_partition.offset = OFFSET_STORED
                # If offset is out of bound, default to setting of auto_offset_reset in config
                elif offset < min_offset or offset >= max_offset:
                    if self._auto_offset_reset.lower() == "earliest":
                        topic_partition.offset = OFFSET_BEGINNING
                    else:
                        topic_partition.offset = OFFSET_STORED
                else:
                    topic_partition.offset = offset
            else:
                raise LookupError(
                    f"Partition out of bounds. Topic: {topic_name}, Requested Partition: {partition_number}, "
                    + f"Max Partition: {max_partition_number}"
                )

            topic_partitions.append(topic_partition)

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
            topic_metadata = self.consumer.list_topics(
                topic=topic_name, timeout=self._consumer_timeout
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

    def _get_watermark_offsets(self, topic_partition, cached=True):
        """
            Retrieve low and high offsets for the specified partition
        Args:
            topic_partition (TopicPartition): a kafka TopicPartition instance

        Returns:
            tuple: min_offset, max_offset for input topic partition
        """
        try:
            min_offset, max_offset = self.consumer.get_watermark_offsets(
                topic_partition, cached=cached
            )
            return min_offset, max_offset
        except Exception as ex:
            self.logger.error(
                "Cannot get partition offset. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                ex,
            )
            raise

    def _set_topics(self, topic_partitions, topic_names):
        """
            Subscribe using topic names or assign using topic partitions
        Args:
            topic_partitions (list(TopicPartition)): list of topic+partitions
            topic_names (list(str)): list of topic names to subscribe to
        """
        try:
            # assign topics with partition/offset to Kafka consumer
            if len(topic_partitions) > 0:
                self.consumer.assign(topic_partitions)
                self.logger.info("Consumer assigned to [%s]", str(topic_partitions))

            # Subscribe topics without partition/offset to Kafka consumer to support load balancing.
            # Regexp pattern subscriptions are supported by prefixing the topic string with "^"
            if len(topic_names) > 0:
                self.consumer.subscribe(topic_names)
                self.logger.info(
                    "Consumer subscribed to topics %s in load balancing mode",
                    topic_names,
                )

            # Subscribe topics using topic pattern.
            # This is to keep backward compatibility with old uspycommon that is implemented using
            # kafka-python api. Topic in Confluent Kafka api supports pattern.
            if self._pattern:
                self.consumer.subscribe(topics=[self._pattern])
                self.logger.info(
                    "Consumer subscribed to pattern %s in load balancing mode",
                    self._pattern,
                )
        except Exception as ex:
            self.logger.error(
                "Failed to initialize kafka consumer. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise

    def _get_messages(self):
        """
            Retrieve message from Kafka server
        Returns:
            list: A list of Kafka Message objects (possibly empty on timeout)
        """
        try:
            # If throttle_max_running_jobs is set, pause consumer if number of active jobs is above threshold
            if self._throttle_max_running_jobs and constant.JOB_MANAGER is not None:
                active_job_count = constant.JOB_MANAGER.get_active_job_count()
                self.logger.debug(f"Num of active_job_count {active_job_count}")
                self.logger.debug(
                    f"Constant.MAX_PARALLEL_JOB {constant.MAX_PARALLEL_JOB}"
                )
                if active_job_count >= constant.MAX_PARALLEL_JOB:
                    if self._paused is False:
                        self.logger.info(
                            f"Max running job reached. Pausing consumer {self.name}"
                        )
                        self.pause()
                        self._paused = True
                # Resume consumer if number of active jobs is below threshold
                else:
                    if self._paused is True:
                        self.logger.info(
                            f"Max running job is below threshold. Resuming consumer {self.name}"
                        )
                        self.resume()
                        self._paused = False

            # Blocking call with a timeout
            # Only pull message from Kafka if consumer is not paused
            if self._paused is False:
                # In case of timeout, an empty list is returned
                return self.consumer.consume(timeout=self._consumer_timeout)
            else:
                # Sleep 0.5 sec to avoid CPU hogging.
                time.sleep(0.5)

            # Return empty list if consumer is paused
            return []
        except Exception as ex:
            self.logger.error(
                "Cannot read from Kafka. Sleeping 30 secs. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            Utils.wait_for(30)
            return []

    def _consume_message(self):
        """
        listen to topic and consumer message
        """
        self.logger.info("Starting to consume messages from Kafka")

        # if a consumer is enabled in configuration,
        # start to consume  messages
        while self.enabled:
            self._process_messages(self._get_messages())

        self._close()

    def _report_metrics(self, msg: KafkaMessage):
        # Calculate and expose consumer lag metrics

        msg_offset = msg.offset()
        topic = msg.topic()
        partition = msg.partition()

        topic_partition = TopicPartition(topic=topic, partition=partition)
        min_offset, max_offset = self._get_watermark_offsets(topic_partition)

        KAFKA_CONSUMER_MIN_OFFSET.labels(
            topic, partition, self._client_id, self._group_id
        ).set(min_offset)
        KAFKA_CONSUMER_MAX_OFFSET.labels(
            topic, partition, self._client_id, self._group_id
        ).set(max_offset)
        KAFKA_CONSUMER_CURRENT_OFFSET.labels(
            topic, partition, self._client_id, self._group_id
        ).set(msg_offset)

        current_lag = max_offset - msg_offset
        self.logger.debug(f"Current Consumer LAG: {current_lag}")
        KAFKA_CONSUMER_LAG.labels(
            topic, partition, self._client_id, self._group_id
        ).set(current_lag)

        if current_lag >= self._consumer_lag_threshold_to_alert:
            KAFKA_CONSUMER_LAG_HIGH.labels(
                topic, partition, self._client_id, self._group_id
            ).set(1)
        else:
            KAFKA_CONSUMER_LAG_HIGH.labels(
                topic, partition, self._client_id, self._group_id
            ).set(0)

    def _report_exception(self, msg: KafkaMessage, ex: Exception, log_msg: str = "", metric: Gauge = None) -> str:
        if metric:
            metric.labels(
                msg.topic(), msg.partition(), self._client_id, self._group_id
            ).inc()
        log_message = (
            f"{log_msg}: "
            f"Kafka Message: {msg.value()}, "
            f"Exception Type: {ex.__class__.__name__}, "
            f"Exception Message: {ex}")
        return log_message

    def _post_to_dlq(self, msg: KafkaMessage) -> bool:
        if self._dlq_producer:
            try:
                self.logger.debug(f"Putting message in DLQ topic: {self._dlq_topic}")
                if payload := msg.value():
                    if self._dlq_producer.send(payload):
                        return True
                    raise RuntimeError("Failed to post to DLQ: error sending!")
                else:
                    raise AttributeError("Failed to post to DLQ: message empty!")
            except Exception as ex:
                self.logger.error(self._report_exception(msg, ex, "Could not post to DLQ"))
        return False

    def _process_messages(self, messages):
        """
            Process message by calling filter and handlers
        Args:
            messages (list(Message)): A list of Kafka Message objects (possibly empty on timeout)
        """
        for message in messages:
            try:
                # Exit loop if consumer is closed due to signal handler
                if not self.enabled:
                    self.logger.info("Exit message processing at message: %s", message)
                    break

                if message is None:
                    continue

                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        self.logger.debug("End of partition reached")
                    else:
                        err_str = f"Error while consuming message: {message.error()}"
                        self.logger.error(err_str)
                        self._commit(message)
                    continue

                # Kafka server returns empty payload if message is malformed
                if len(message.value()) == 0:
                    err_str = f"Error while consuming message: {message.error()}"
                    self.logger.error(err_str)
                    self._commit(message)
                    continue

                # Calculate and expose consumer lag metrics
                self._report_metrics(message)

                # Deserialize message key and value
                try:
                    message.set_key(int.from_bytes(message.key(), "big") if message.key() else 0)
                    message.set_value(json.loads(message.value().decode("utf-8")) if message.value() else "")
                except Exception as ex:
                    self.logger.error(self._report_exception(
                        message, ex, "Exception thrown during message deserialization"))
                    # there are some cases where this might fail...
                    #   e.g. the producer hits the same problem with the message value,
                    #   but it's simplest to just try anyway
                    self._post_to_dlq(message)
                    self._commit(message)
                    continue

                topic = message.topic()
                partition = message.partition()

                try:
                    start_time = round(time.time() * 1000)
                    # Filter message, only one filter is allowed
                    res = self._msg_filter(message)
                    end_time = round(time.time() * 1000)
                    KAFKA_FILTER_TIME.labels(
                        topic, partition, self._client_id, self._group_id
                    ).observe(end_time - start_time)
                    KAFKA_FILTER_EXCEPTION.labels(
                        topic, partition, self._client_id, self._group_id
                    ).set(0)
                    if not res:
                        self._commit(message)
                        continue
                except Exception as ex:
                    # Proceeding to the next message after reporting the exception and optionally posting to DLQ
                    self.logger.error(self._report_exception(
                        message, ex, "Exception thrown from filter", KAFKA_FILTER_EXCEPTION))
                    self._post_to_dlq(message)
                    # We DO commit here because we won't do anything else with this message.
                    self._commit(message)
                    continue

                # process messages. All handlers will be called
                # todo: once we have an envelope for the context, then we'll want one DLQ message per handler ex
                #  until then, we'll only post the original message to the DLQ one time.
                posted_to_dlq = False
                for msg_handler in self._msg_handlers:
                    try:
                        start_time = round(time.time() * 1000)
                        msg_handler(message)
                        end_time = round(time.time() * 1000)
                        KAFKA_HANDLER_TIME.labels(
                            topic, partition, self._client_id, self._group_id
                        ).observe(end_time - start_time)
                        KAFKA_HANDLER_EXCEPTION.labels(
                            topic, partition, self._client_id, self._group_id
                        ).set(0.0)
                    except Exception as ex:
                        # Proceeding to the next handler after logging the exception and optionally posting to DLQ
                        self.logger.error(self._report_exception(
                            message, ex, "Exception thrown from handler", KAFKA_HANDLER_EXCEPTION))
                        if not posted_to_dlq:
                            posted_to_dlq = self._post_to_dlq(message)
                        # We DON'T commit here because we need to ensure all the handlers get a chance with the message.
            except Exception as ex:
                self.logger.error(self._report_exception(
                    message, ex, "Exception thrown from Kafka message processing"))
                self._post_to_dlq(message)
                self._commit(message)
                continue
            else:
                if self._enable_auto_commit is not True:
                    # if auto commit isn't enabled, manually commit message
                    self._commit(message)

    def _close(self):
        """
        Close down and terminate the Kafka Consumer.
        """
        self.consumer.unsubscribe()
        self.consumer.unassign()
        self.logger.info(
            "Unsubscribed KafkaConsumer %s in thread %s", self.name, self._thrd_name
        )
        self.consumer.close()
        # TODO: Need to clear only when no messages is being processed. Otherwise SEGV
        # self._msg_handlers.clear()
        self.logger.info(
            "Closed KafkaConsumer %s in thread %s", self.name, self._thrd_name
        )

    def _commit(self, message):
        """
            Commit message
        Args:
            message (Message): a message to be committed
        """
        try:
            self.consumer.commit(message)
        except Exception as ex:
            self.logger.error(self._report_exception(message, ex, "Cannot commit message"))

    def stop(self):
        """
        Stop the Kafka Consumer.
        """
        self.logger.info("Stop KafkaConsumer %s", self.name)
        self.enabled = False
        self.started = False

    def append_to_group_id(self, ext):
        """
        Append additional string to consumer group_id

        Args:
            ext (str): additional string that will be appended to existing group_id
        """
        if self.started:
            raise ValueError("Cannot append id to group_id of a running consumer")

        append_id = str(ext)
        if self._group_id:
            self._group_id = self._group_id + "-" + append_id
        else:
            self._group_id = append_id

    def append_to_client_id(self, ext):
        """
        Append additional string to consumer client_id

        Args:
            ext (str): additional string that will be appended to existing client_id
        """
        if self.started:
            raise ValueError("Cannot append id to client_id of a running consumer")

        append_id = str(ext)
        if self._client_id:
            self._client_id = self._client_id + "-" + append_id
        else:
            self._client_id = append_id

    def pause(self):
        """
        Pause the Kafka Consumer.
        """
        self.consumer.pause(self.consumer.assignment())
        self.logger.debug(f"Paused KafkaConsumer {self.name}")

    def resume(self):
        """
        Resume the Kafka Consumer.
        """
        self.consumer.resume(self.consumer.assignment())
        self.logger.debug(f"Resumed KafkaConsumer {self.name}")

    def seek(self, topic: str, partition: int, offset: int = None):
        """
            Set consume position for partition to offset.
            The offset may be an absolute (>=0) or a logical offset (OFFSET_BEGINNING et.al).
        Args:
            topic (str): topic name
            partition (int): partition number
            offset (int, optional): offset. Defaults to None.
        Raises:
            KafkaException
        """
        topic_partition = TopicPartition(
            topic=topic, partition=partition, offset=offset
        )
        self.consumer.seek(topic_partition)

    def get_topic_partition_offsets(
        self, topic: str, partition: int
    ) -> tuple[int, int]:
        """
            Retrieve low and high offsets for the specified partition
        Args:
            topic (str): topic name
            partition (int): partition number
        Returns:
            (int, int): tuple, min_offset, max_offset for input topic, partition
        Raises:
            KafkaException
        """
        topic_partition = TopicPartition(topic=topic, partition=partition)
        return self._get_watermark_offsets(topic_partition, cached=False)

    def get_assignment(self) -> TopicPartition:
        """
            Get the current partition assignment.
        Returns:
            list: list of TopicPartition
        Raises:
            RuntimeError: Failed to get assignment for consumer
        """
        try:
            return self.consumer.assignment()
        except Exception as ex:
            raise RuntimeError(
                f"Failed to get assignment for consumer {self.name}"
            ) from ex
