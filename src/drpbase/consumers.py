################################################################################
# Copyright (c) 2017-2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
KConsumerClient is used to create consumers based on configuration
"""
import os
import sys
import importlib
import inspect
import logging

from . import constant
from .utils import Utils

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from isgkafka.consumer import KConsumer
from isgkafka.messagehandler import AbcMessageHandler
from isgkafka.messagefilter import AbcMessageFilter


class KConsumers:
    """
    KConsumers class
    """

    def __init__(self, kafka_cfg):
        """
        Create a new KConsumerClient based on Kafka configuration

        :param kafka_cfg: A dictionary that contains kafka configuration
        """
        self._consumers = {}
        # track all registered object ids.
        # One object is not allowed to be registered twice
        # either in the same consumer or another consumer
        self._registered_ids = set()

        self.consumer_cfgs = kafka_cfg.get("consumers", None)

        self.logger = logging.getLogger(constant.LOGGER_NAME)

        # make sure configuration of consumers exist
        # Only if kafka_cfg['consumers'] is present, the framework constructs KConsumers
        if self.consumer_cfgs is None:
            self.logger.error("No consumer is defined")
            raise ValueError("No consumer is defined")

        for consumer_cfg in self.consumer_cfgs:
            # Skip consumer that isn't enabled.
            enabled = consumer_cfg.get("enabled", False)
            if not enabled:
                continue

            # Set consumer bootstrap_server
            # if there doesn't exist bootstrap_servers in consumer setting itself,
            # get it from Kafka setting
            if consumer_cfg.get("bootstrap_servers", None) is None:
                consumer_cfg["bootstrap_servers"] = kafka_cfg.get(
                    "bootstrap_servers", None
                )

            consumer_cfg["ssl_ca_location"] = kafka_cfg.get("ssl_ca_location", None)
            consumer_cfg["ssl_certificate_location"] = kafka_cfg.get(
                "ssl_certificate_location", None
            )
            consumer_cfg["ssl_key_location"] = kafka_cfg.get("ssl_key_location", None)

            self._init_consumer(consumer_cfg)

    def _init_consumer(self, consumer_cfg):
        try:
            name = Utils.get_config_value(consumer_cfg, "name", is_required=True)

            kConsumer = KConsumer(consumer_cfg)

            # Another consumer using the same name is not allowed,
            # If it happens, ValueError is raised.
            if name in self._consumers.keys():
                raise ValueError(
                    f"Consumer: {name} has already been created. "
                    + "Please check duplicated consumer names in config"
                )

            # Add consumer to dictionary
            self._consumers.update({name: kConsumer})

            msg_filter = self._get_msg_filter(consumer_cfg)
            msg_handlers = self._get_msg_handlers(consumer_cfg)

            # register message filter and handlers if found in configuration file
            if msg_filter:
                self.register_filter(name, msg_filter)

            if msg_handlers:
                self.register_handlers(name, msg_handlers)
        except Exception as ex:
            self.logger.error(
                "Cannot create a consumer. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise Exception("Cannot create a consumer") from ex

    def _get_msg_filter(self, consumer_cfg):
        filter_class_instance = None
        logger = logging.getLogger(constant.LOGGER_NAME)
        message_filter = consumer_cfg.get("filter_module", None)

        # if a message filter is not defined in configuration file, return None
        if message_filter is None:
            return None

        filter_module = importlib.import_module(message_filter)

        # Check all the classes in the import module
        for n, _ in inspect.getmembers(filter_module, inspect.isclass):
            filter_class = getattr(filter_module, n)

            # Skip class that doesn't implement AbcMessageFilter
            if inspect.isabstract(filter_class) or not issubclass(
                filter_class, AbcMessageFilter
            ):
                continue

            # When the first filter class is found, create one instance and break the loop.
            # We will only allow one message filter class.
            filter_class_instance = filter_class()
            logger.info("found filter class %s", filter_class.__name__)
            break

        return filter_class_instance

    def _get_msg_handlers(self, consumer_cfg):
        msg_handler_instances = []
        logger = logging.getLogger(constant.LOGGER_NAME)

        handlers = consumer_cfg.get("handlers", None)
        # if message handlers are not defined in configuration file, return empty list.
        if handlers is None or len(handlers) == 0:
            return msg_handler_instances

        for handler in handlers:
            module = handler.get("handler_module")
            handler_module = importlib.import_module(module)

            # Check all the classes in the import module
            for n, _ in inspect.getmembers(handler_module, inspect.isclass):
                handler_class = getattr(handler_module, n)
                # Skip class that doesn't implement AbcMessageHandler
                if inspect.isabstract(handler_class) or not issubclass(
                    handler_class, AbcMessageHandler
                ):
                    continue

                # Create found message handler instances and add them to the list
                logger.info("found handler class %s", handler_class.__name__)
                msg_handler_instances.append(handler_class())

        return msg_handler_instances

    def get_by_name(self, name):
        """
        Get a consumer using its name
        Args:
            name (str): consumer name

        Returns:
            KConsumer: a consumer instance or None
        """
        if len(self._consumers):
            return self._consumers.get(name, None)

        return None

    def stop_consumer(self, name):
        """Stop one consumer using its name

        Args:
            name (str): consumer name defined in configuration file

        Raises:
            ValueError: Consumer not found
        """
        # stop one consumer using its name
        if len(self._consumers):
            consumer = self._consumers.get(name, None)
            if consumer is not None:
                if consumer.enabled:
                    consumer.stop()
            else:
                self.logger.error("Consumer %s not found", name)
                raise ValueError(f"Consumer: {name} not found")
        else:
            self.logger.error("Consumer %s not found", name)
            raise ValueError(f"Consumer: {name} not found")

    def stop_consumers(self):
        """
        Stop all the consumers
        """
        for consumer in self._consumers.values():
            if consumer.enabled:
                consumer.stop()

    def start_consumer(self, name):
        """Start a consumer using its name

        Args:
            name (str): consumer name defined in configuration file

        Raises:
            Exception: Cannot start a consumer
        """
        try:
            consumer = self.get_by_name(name)
            consumer.start()
        except Exception as ex:
            self.logger.error(
                "Cannot start consumer: %s. Exception type: %s, Message: %s",
                name,
                ex.__class__.__name__,
                str(ex),
            )
            raise Exception("Cannot start a consumer") from ex

    def start_consumers(self):
        """Start all consumers

        Raises:
            Exception: Cannot start consumers
        """
        try:
            for consumer in self._consumers.values():
                consumer.start()
        except Exception as ex:
            self.logger.error(
                "Cannot start consumers. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise Exception("Cannot start consumers") from ex

    def register_filter(self, name, msg_filter):
        """Register message filter using consumer name

        Args:
            name (str): consumer name defined in configuration file
            msg_filter (AbcMessageFilter): an instance that implements AbcMessageFilter

        Raises:
            ValueError: consumer not found
        """
        consumer = self.get_by_name(name)
        if consumer:
            if not self._is_registered(msg_filter):
                consumer.register_filter(msg_filter)
        else:
            raise ValueError(f"Consumer: {name} not found")

    def register_handlers(self, name, msg_handlers):
        """Register a list of handlers using consumer name

        Args:
            name (str): consumer name defined in configuration file
            msg_handlers (AbcMessageHandler):a list of instances that implement AbcMessageHandler

        Raises:
            ValueError: consumer not found
        """
        consumer = self.get_by_name(name)
        if consumer:
            for msg_handler in msg_handlers:
                # check if any of handlers has been registered.
                # If so, exception is raised.
                self._is_registered(msg_handler)

            consumer.register_handlers(msg_handlers)
        else:
            raise ValueError(f"Consumer: {name} not found")

    def _is_registered(self, obj):
        """Check if object has been registered in consumers

        Args:
            obj (object): filter or handlers

        Raises:
            ValueError: This Object id has already been registered.

        Returns:
            boolean: False
        """
        oid = id(obj)
        if oid in self._registered_ids:
            # If object has been registered before, raise exception
            raise ValueError(
                f"This Object id: {oid} has already been registered. "
                + f"Class: {obj.__class__.__name__}"
            )

        self._registered_ids.add(oid)

        return False

    def append_to_group_id(self, name, ext):
        """
        Append additional string to consumer group_id
        Args:
            name (string): name of a consumer
            ext (str): additional string that will be appended to existing group_id

        Raises:
            ValueError: Consumer not found
        """
        consumer = self.get_by_name(name)
        if consumer:
            consumer.append_to_group_id(ext)
        else:
            raise ValueError(f"Consumer: {name} not found")

    def append_to_client_id(self, name, ext):
        """
        Append additional string to consumer client_id

        Args:
            name (string): name of a consumer
            ext (str): additional string that will be appended to existing client_id

        Raises:
            ValueError: Consumer not found
        """
        consumer = self.get_by_name(name)
        if consumer:
            consumer.append_to_client_id(ext)
        else:
            raise ValueError(f"Consumer: {name} not found")
