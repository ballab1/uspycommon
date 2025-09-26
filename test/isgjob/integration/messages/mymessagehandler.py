################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import logging
from drpbase import constant
from isgkafka.messagehandler import AbcMessageHandler


class MessageHandler1(AbcMessageHandler):
    def __init__(self):
        self.logger = logging.getLogger(constant.LOGGER_NAME)

    def handle_messages(self, message):
        if message.topic() == "testTopic4":
            payload = message.value()
            job_generate_name = payload.get("job_generate_name")
            user_specified_job_name = payload.get("user_specified_job_name", "")
            job_id = payload.get("job_id")
            containers = payload.get("containers")
            labels = payload.get("labels")
            delete_existing_job = payload.get("delete_existing_job", True)

            # Create jobs
            # Provide container argument as a list of dictionary with the following format.
            # {'name': 'container_name', 'args': [arg1, arg2]}
            self.logger.info(
                f"Creating job with {job_generate_name}, {job_id}, containers: {containers}, labels: {labels}, Offset: {message.offset()}"
            )
            constant.JOB_MANAGER.create_job(
                job_generate_name,
                delete_existing_job,
                user_specified_job_name=user_specified_job_name,
                job_id=job_id,
                containers=containers,
                labels=labels,
            )
