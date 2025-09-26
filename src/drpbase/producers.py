################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
"""
    producers.py
    -------------
    This module contains the KProducers class that has a dictionary with
    producer name and its instance. The key of that dictionary is name of producer
    and the value of each key is its corresponding instance.
"""

import os
import sys
import logging

from . import constant

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from isgkafka.producer import KProducer


class KProducers:
    """Kafka producers contains a dictionary with Kafka producers and their names.
    You can retrieve a producer by producer name
    """

    def __init__(self, kafka_cfg):
        """
        Create a new KProducers instance based on Kafka configuration
        """
        self.producers = {}
        self.logger = logging.getLogger(constant.LOGGER_NAME)

        producer_cfgs = kafka_cfg.get("producers", None)

        # make sure configuration of producers exist
        if producer_cfgs is None:
            self.logger.error(
                "Tried to create KProducer without supplying configuration."
            )
            raise ValueError(
                "Tried to create KProducer without supplying configuration."
            )

        for producer_cfg in producer_cfgs:
            # Set bootstrap server for producer config.
            # if there doesn't exist bootstrap_servers in producer setting itself,
            # get it from Kafka setting
            if producer_cfg.get("bootstrap_servers", None) is None:
                producer_cfg["bootstrap_servers"] = kafka_cfg.get(
                    "bootstrap_servers", None
                )

            producer_cfg["ssl_ca_location"] = kafka_cfg.get("ssl_ca_location", None)
            producer_cfg["ssl_certificate_location"] = kafka_cfg.get(
                "ssl_certificate_location", None
            )
            producer_cfg["ssl_key_location"] = kafka_cfg.get("ssl_key_location", None)

            # get producer name and use as a key in dictionary
            name = producer_cfg.get("name", None)
            if name is None or len(name) == 0:
                self.logger.error("Producer name is required")
                raise ValueError("Producer name is required")

            try:
                # Create producer and update dictionary
                self.producers.update({name: KProducer(producer_cfg)})
            except Exception as ex:
                self.logger.error(
                    "Cannot update producer list. Exception type: %s, Message: %s",
                    ex.__class__.__name__,
                    str(ex),
                )
                raise ex

    def get_by_name(self, name: str):
        """
        Get a producer by name
        Args:
            name (str): name of producer

        Returns:
            KProducer: a producer instance
        """
        if self.producers is not None:
            try:
                return self.producers[name]
            except KeyError:
                self.logger.error(f"Producer {name} not found")

        return None

    def close_producer(self, name: str):
        """
        Close a producer by name
        Args:
            name (str): name of producer
        """
        producer = self.get_by_name(name)
        if producer is not None and self.producers is not None:
            producer.close()
            self.producers.pop(name)
        else:
            self.logger.warning(f"Producer {name} not found")

    def close_producers(self):
        """
        Close all producers
        """
        if self.producers is None:
            return

        for producer in self.producers.values():
            producer.close()

        self.producers.clear()
        self.producers = None
