#!/usr/bin/env python3

#############################################################################
# Copyright (c) 2017-2021 Dell Inc. or its subsidiaries. All Rights Reserved.
#############################################################################

"""Script to generate kafka json payload"""

import json
import sys
import argparse
import uuid
from kafka import KafkaProducer


def _initialize(kafka_server):
    if kafka_server == "localhost":
        kafka_prod = KafkaProducer(
            bootstrap_servers=["localhost:9092"],
            retries=5,
            max_block_ms=30000,
            value_serializer=str.encode,
        )
    elif kafka_server == "test":
        kafka_prod = KafkaProducer(
            bootstrap_servers=["broker1.cec.lab.emc.com:9092"],
            retries=5,
            max_block_ms=30000,
            value_serializer=str.encode,
        )
    else:
        kafka_prod = KafkaProducer(
            bootstrap_servers=[kafka_server + ":9092"],
            retries=5,
            max_block_ms=30000,
            value_serializer=str.encode,
        )
    return kafka_prod


def _send_message(**args):
    if args["dryrun"] is False:
        kafka_prod = _initialize(args["kafka"])

    with open(args["template"], "r") as file:
        data = file.read()
    mesg_data = json.loads(data)
    mesg_data["handler_id"] = args["handler_id"]
    mesg_data["sleep"] = args["sleep"]
    mesg_data["exception"] = args["exception"]
    mesg_data["record_id"] = str(uuid.uuid4())

    # mesg_data = json.loads(data)
    mesg_data_json = json.dumps(mesg_data)
    if args["dryrun"] is False:
        kafka_prod.send(args["topic"], mesg_data_json)
        print("Sending to %s : %s" % (args["topic"], mesg_data_json))
        kafka_prod.close()
    elif args["dryrun"] is True:
        print(
            "[Dryrun] Sending to kafka broker=%s, topic=%s : %s"
            % (args["kafka"], args["topic"], mesg_data_json)
        )


def main():
    """main"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun", action="store_true", help="Dry-run mode")
    parser.add_argument(
        "--template",
        action="store",
        type=str,
        help="Message template",
        default="template.txt",
    )
    required_args = parser.add_argument_group("required arguments")
    required_args.add_argument(
        "--topic", action="store", type=str, help="Kafka topic", required=True
    )
    required_args.add_argument(
        "--kafka", action="store", type=str, help="Kafka server", required=True
    )
    required_args.add_argument(
        "--sleep", action="store", type=int, help="Sleep time", required=True
    )
    required_args.add_argument(
        "--exception", action="store", type=bool, help="Throw exception", required=True
    )
    required_args.add_argument(
        "--handler_id", action="store", type=int, help="Throw exception", required=True
    )

    args = parser.parse_args(None if sys.argv[1:] else ["-h"])
    _send_message(**vars(args))


if __name__ == "__main__":
    main()
