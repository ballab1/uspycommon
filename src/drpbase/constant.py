################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

LOGGER_NAME = "microservice"
LOG_LEVEL = "INFO"
CONFIG_PATH = "/etc/config"
SLEEP_TIME = 3600  # seconds
ROOT_FILE = "configroot"
CONFIGURATION = None
FRAMEWORK = None
DEFAULT_WRONG_GAUGE_METRIC_VALUE = -64.0
SIGNAL_HANDLER_WAIT_TIME = 50  # seconds
DEFAULT_CONSUMER_LAG_THRESHOLD_TO_ALERT = 300
MONITOR = None
CONSUMERS = None
GITHUB = None
GITHUB_APPS = None
PRODUCERS = None
INTERRUPTED = False
JOB_MANAGER = None
STATUS_REPORTER = None
MAX_ATTEMPTS = 3
# Timeout used in validating Kafka connection when starting up
KAFKA_VALIDATION_TIMEOUT = 20.0  # seconds
ATTEMPT_INTERVAL = 5  # seconds
# The maximum running time for a job before API issues error in log.
JOB_MAX_RUNNING_TIME = 1800  # seconds

# Job manager will delete a failed job
# after KEEPING_SUCCEEDED_JOB_TIME counting from job start time.
KEEPING_FAILED_JOB_TIME = 240  # seconds

# Job manager will delete a successful jobs
# after KEEPING_SUCCEEDED_JOB_TIME counting from job complete time.
KEEPING_SUCCEEDED_JOB_TIME = 120  # seconds

# Maximum number of active jobs, spawned by this microservice.
# Once the number of active jobs reaches this number,
# KafkaConsumer is paused.
MAX_PARALLEL_JOB = 3

# A label using JOB_MANAGER_NAME and namespace will be created and assigned
# to each job that job manager spawns. Job manager uses that label to monitor its jobs.
# If running in local VM, DEV_NAMESPACE has to be defined
# and it will be used to form that job label.
JOB_MANAGER_NAME = None

# The method that job manager calls back to the microservice
# This method only accepts one parameter (V1Job).
ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = None

# Development namespace
DEV_NAMESPACE = None
