################################################################################
# Copyright (c) 2017-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################


import logging
import time
import sys
import signal
from functools import partial
from deprecated import deprecated
from . import logger
from .configurationmanager import ConfigurationManager
from . import constant
from . import monitor
from .producers import KProducers
from .consumers import KConsumers
from .jobmanager import JobManager
from .github import GithubInstance
from .githubappinstances import GithubAppInstances
from .statusreporter import StatusReporter


def usage():
    print(__doc__)


class UsFramework(object):
    """1. Allocates a logger to be used for logging.
    2. Calls configuration manager to combine all *.yml files, located under the input directory `config_path`
       to produce a single dictionary.
    3. Registers and manages KafkaMessageHandlers for a KafkaConsumer
    """

    def create(
        self,
        config_path=constant.CONFIG_PATH,
        logger_name=constant.LOGGER_NAME,
        base_extra={},
        config=None,
    ):
        try:
            self.pre_stop_func = None

            constant.LOGGER_NAME = logger_name
            self.logger = logger.setup_logger(
                constant.LOGGER_NAME, constant.LOG_LEVEL, base_extra=base_extra
            )

            if config is None:
                constant.CONFIG_PATH = config_path
                constant.CONFIGURATION = ConfigurationManager(
                    config_path, constant.LOGGER_NAME
                )
            else:
                constant.CONFIGURATION = config

            # Start monitor which will allows Prometheus to scrape and get the relevant data
            if constant.CONFIGURATION.get("framework", None):
                if constant.CONFIGURATION.get("framework").get("log_level", None):
                    constant.LOG_LEVEL = constant.CONFIGURATION.get("framework").get(
                        "log_level"
                    )
                    # set log level to the desired level
                    self.logger.setLevel(constant.LOG_LEVEL)

                # Retrieve framework settings if available
                if constant.CONFIGURATION.get("framework").get("max_attempts", None):
                    constant.MAX_ATTEMPTS = constant.CONFIGURATION.get("framework").get(
                        "max_attempts"
                    )
                    self.logger.info(
                        "Framework MAX_ATTEMPTS = %d", constant.MAX_ATTEMPTS
                    )

                if constant.CONFIGURATION.get("framework").get(
                    "attempt_interval", None
                ):
                    constant.ATTEMPT_INTERVAL = constant.CONFIGURATION.get(
                        "framework"
                    ).get("attempt_interval")
                    self.logger.info(
                        "Framework ATTEMPT_INTERVAL = %d", constant.ATTEMPT_INTERVAL
                    )

                if constant.CONFIGURATION.get("framework").get("monitor", None):
                    self.logger.info("Starting default monitoring")
                    self.monitor = monitor.Monitor(
                        constant.CONFIGURATION["framework"]["monitor"]
                    )
                    constant.MONITOR = self.monitor
                    # If framework has some extra metrics to monitor, it will be done now.
                    monitor_config = constant.CONFIGURATION["framework"]["monitor"]
                    metrics = monitor_config.get("metrics", None)
                    if metrics:
                        constant.MONITOR.register_metrics(metrics)
                    else:
                        self.logger.info(
                            "Only framework monitoring has started but no metrics specified."
                        )
                else:
                    self.logger.warning(
                        "Framework monitoring is not specified in configuration. Monitoring will be skipped."
                    )

                if constant.CONFIGURATION.get("framework").get(
                    "signal_handler_wait_time", None
                ):
                    constant.SIGNAL_HANDLER_WAIT_TIME = constant.CONFIGURATION[
                        "framework"
                    ]["signal_handler_wait_time"]
                    self.logger.info(
                        "Framework SIGNAL_HANDLER_WAIT_TIME = %d",
                        constant.SIGNAL_HANDLER_WAIT_TIME,
                    )
                else:
                    self.logger.info(
                        "Framework signal_handler_wait_time setting is not specified in configuration. Using default value: %d",
                        constant.SIGNAL_HANDLER_WAIT_TIME,
                    )
            else:
                self.logger.error("Framework is not specified in configuration.")

            self.logger.info("Framework LOG_LEVEL = %s", constant.LOG_LEVEL)

            self._create_kafka()

            self._create_github()

            self._create_github_apps()

            self._create_jobmanager()

            self._create_status_report()

            # register signal handlers to exit gracefully
            wait_time = (
                constant.SIGNAL_HANDLER_WAIT_TIME + 10
            )  # add 10 seconds buffer to allow clean shutdown
            self.signal_handler = None

            signal.signal(
                signal.SIGINT, partial(self._signal_term_handler, wait_time=wait_time)
            )
            signal.signal(
                signal.SIGABRT, partial(self._signal_term_handler, wait_time=wait_time)
            )
            signal.signal(
                signal.SIGTERM, partial(self._signal_term_handler, wait_time=wait_time)
            )

        except Exception as ex:
            if self.logger:
                self.logger.error(
                    "Failed to initialize the framework. Please report it to DRP."
                )
                self.logger.error(
                    "Exception thrown. Exception type: %s, Exception message: %s",
                    ex.__class__.__name__,
                    str(ex),
                )
            else:
                print(
                    "Failed to initialize the framework. Please report it to DRP.\nError msg=%s\nExiting",
                    str(ex),
                )
            exit(1)

        constant.FRAMEWORK = self

    @staticmethod
    @deprecated(reason="Replaced with the same method in utils.py")
    def get_secret(key, mount_path="/etc/secrets/", retry_attempt=0):
        """Returns the secret value stored against the input token. If no stored value is found,
        None is returned. If retry_attempt is set to an integer value greater than 0, the framework
        will refresh the stored secret values from the vault and return the updated value. Therefore,
        setting retry_attempt to non-zero may cause a delay. The application will set retry_attempt to a
        non-zero value, only when it finds out that the returned secret value is stale,
        i.e., the application got an authorization error using the returned value.
        Currently, all values, greater than 0 are ignored.
        """

        secret = None
        lgr = logging.getLogger(constant.LOGGER_NAME)
        try:
            if retry_attempt > 0:
                pass  # Call restful api of secret-manager to refresh app-secret. Not implemented yet.

            if mount_path[-1] != "/":
                mount_path = mount_path + "/"

            with open(mount_path + key, "r", encoding="utf-8") as f:
                secret = f.read()
        except (IOError, FileNotFoundError) as ex:
            lgr.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )

        return secret

    def _create_kafka(self):
        """
        Create Kafka consumers and producers from configuration if presented.

        Raises:
            ValueError: Error when creating Kafka with supplied configuration
        """
        try:
            # get kfaka configuration
            config = constant.CONFIGURATION.get("kafka", None)
            if config:
                if config.get("producers", None):
                    self.kproducers = KProducers(config)
                    constant.PRODUCERS = self.kproducers

                if config.get("consumers", None):
                    self.kconsumers = KConsumers(config)
                    constant.CONSUMERS = self.kconsumers
        except Exception as ex:
            self.logger.error("Error when creating Kafka with supplied configuration:")
            self.logger.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ValueError("Error when creating Kafka with supplied configuration.")

    def _create_github(self):
        """
        Create GitHub instance from configuration if presented.

        Raises:
            ValueError: Error when creating Github instance with supplied configuration
        """
        try:
            # get github configuration
            config = constant.CONFIGURATION.get("github", None)
            if config:
                GithubInstance(config)
        except Exception as ex:
            self.logger.error("Error when creating Github with supplied configuration:")
            self.logger.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ValueError("Error when creating Github with supplied configuration.")

    def _create_github_apps(self):
        """
        Create GitHub App instances from configuration if present.
        Raises:
            ValueError: Error when creating Github instance with supplied configuration
        """
        try:
            # get github configuration
            config = constant.CONFIGURATION.get("github_app", None)
            if config:
                GithubAppInstances(config)
        except Exception as ex:
            self.logger.error("Error when creating Github with supplied configuration:")
            self.logger.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ValueError(
                "Error when creating Github App Dict with supplied configuration."
            )

    def _create_jobmanager(self):
        """
        Create job manager, which is used by the application to create K8s jobs

        Raises:
            ValueError: Error when creating JobManager with supplied configuration
        """
        try:
            # get jobs configuration
            jobmanager_config = constant.CONFIGURATION.get("jobmanager", None)

            if jobmanager_config:
                # get job manager setting
                if jobmanager_config.get("job_monitor_sleep_time", None):
                    constant.JOB_MONITOR_SLEEP_TIME = jobmanager_config.get(
                        "job_monitor_sleep_time"
                    )
                    self.logger.info(
                        "Framework JOB_MONITOR_SLEEP_TIME = %d",
                        constant.JOB_MONITOR_SLEEP_TIME,
                    )

                if jobmanager_config.get("keeping_failed_job_time", None):
                    constant.KEEPING_FAILED_JOB_TIME = jobmanager_config.get(
                        "keeping_failed_job_time"
                    )
                    self.logger.info(
                        "Framework KEEPING_FAILED_JOB_TIME = %d",
                        constant.KEEPING_FAILED_JOB_TIME,
                    )

                if jobmanager_config.get("keeping_succeeded_job_time", None):
                    constant.KEEPING_SUCCEEDED_JOB_TIME = jobmanager_config.get(
                        "keeping_succeeded_job_time"
                    )
                    self.logger.info(
                        "Framework KEEPING_SUCCEEDED_JOB_TIME = %d",
                        constant.KEEPING_SUCCEEDED_JOB_TIME,
                    )

                if jobmanager_config.get("job_manager_name", None):
                    constant.JOB_MANAGER_NAME = jobmanager_config.get(
                        "job_manager_name"
                    )
                    self.logger.info(
                        "Framework JOB_MANAGER_NAME = %s", constant.JOB_MANAGER_NAME
                    )
                else:
                    raise ValueError("job_manager_name isn't defined")

                if jobmanager_config.get("dev_namespace", None):
                    constant.DEV_NAMESPACE = jobmanager_config.get("dev_namespace")
                    self.logger.info(
                        "Framework DEV_NAMESPACE = %s", constant.DEV_NAMESPACE
                    )

                if jobmanager_config.get("job_max_running_time", None):
                    constant.JOB_MAX_RUNNING_TIME = jobmanager_config.get(
                        "job_max_running_time"
                    )
                    self.logger.info(
                        "Framework JOB_MAX_RUNNING_TIME = %d",
                        constant.JOB_MAX_RUNNING_TIME,
                    )

                if jobmanager_config.get("max_parallel_job", None):
                    constant.MAX_PARALLEL_JOB = jobmanager_config.get(
                        "max_parallel_job"
                    )
                    self.logger.info(
                        "Framework MAX_PARALLEL_JOB = %d", constant.MAX_PARALLEL_JOB
                    )

                if jobmanager_config.get("jobs", None) is None:
                    raise ValueError("job configuration not found")

                # Even when running in K8s, if namespace cannot be found,
                # we will be concluding that the microservice is running on a VM
                constant.JOB_MANAGER = JobManager(jobmanager_config.get("jobs"))

                # create a thread to watch jobs in the namespace
                # After job manager has been constructed, we start watching jobs
                constant.JOB_MANAGER.start()
            else:
                self.logger.info(
                    "No job configuration specified. JobManager not started."
                )

        except Exception as ex:
            self.logger.error(
                "Error when creating JobManager with supplied configuration. \
                              Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ValueError(
                "Error when creating JobManager with supplied configuration."
            )

    def _create_status_report(self):
        """
        Create status reporter which sends result to aggregator service.

        Raises:
            ValueError: Error when creating Report with supplied configuration
        """
        try:

            # get status_reporter configuration
            config = constant.CONFIGURATION.get("status_reporter", None)
            if config:
                constant.STATUS_REPORTER = StatusReporter(config)

        except Exception as ex:
            self.logger.error(
                "Error when creating status reporter with supplied configuration:"
            )
            self.logger.error(
                "Exception thrown. Exception type: %s, Exception message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ex

    @deprecated(reason="Replaced with the same method in utils.py")
    def wait(self):
        """_wait forever. The function will exit if interrupted flag is True"""
        while not constant.INTERRUPTED:
            time.sleep(constant.SIGNAL_HANDLER_WAIT_TIME)

    @deprecated(reason="Replaced with the same method in utils.py")
    def wait_for(self, wait_time=constant.SLEEP_TIME):
        """
        Wait for specified number of seconds

        Args:
            wait_time (integer, optional): number of seconds. Defaults to constant.SLEEP_TIME.
        """
        already_wait = 0

        while not constant.INTERRUPTED and already_wait < wait_time:
            if not already_wait:
                self.logger.debug("Sleeping %s seconds", wait_time)
            time.sleep(constant.SIGNAL_HANDLER_WAIT_TIME)
            already_wait += constant.SIGNAL_HANDLER_WAIT_TIME

    def register_pre_stop(self, pre_stop_func, *args, **kwargs):
        """
        Register a pre_stop function that will be called when the microservice receives a signal for shutdown and after consumers are stopped

        Args:
            pre_stop_func (func): a function to be called
        """
        self.pre_stop_func = partial(pre_stop_func, *args, *kwargs)

    def _signal_term_handler(self, signnum, frame, wait_time):
        """Signal handling function. That is called when the following signals are caught.
        signal.SIGINT
        signal.SIGABRT
        signal.SIGTERM

        It will also set constant.INTERRUPTED = True
        Args:
            wait_time (int): Time in seconds to wait for consumers to stop
        """
        constant.INTERRUPTED = True
        try:
            self.shutdown(signnum=signnum, wait_time=wait_time)
        except Exception as ex:
            self.logger.warning(f"Exited with exception: {ex}")
        finally:
            sys.exit(signnum)

    def shutdown(self, signnum: int = 0, wait_time: int = 30):
        """
        Gracefully shuts down the framework.
        Programmatic clients have to make sure to complete the shutdown process.
        Used in two modes :
            1 - Normal operation mode , called when the microservice receives a signal for shutdown
            2 - External signal hook , when sigterms are intercepted by higher level process (like uvicorn)

        Args:
            signnum (int): The signal number that triggered the shutdown (default: 0).
            wait_time (int): The number of seconds to wait for consumers to stop (default: 30).
        """
        self.logger.info("Start graceful shutdown process")
        try:
            # Close all producers if exist.
            if hasattr(self, "kproducers") and self.kproducers is not None:
                self.kproducers.close_producers()
                self.logger.info("Close all producers")

            # Close all consumers if exist.
            if hasattr(self, "kconsumers") and self.kconsumers is not None:
                self.kconsumers.stop_consumers()
                # wait_time in seconds
                self.logger.info(f"Waiting for consumers to stop {wait_time} seconds")
                time.sleep(wait_time)

            # Call external signal handler function if provided
            if hasattr(self, "pre_stop_func") and self.pre_stop_func is not None:
                self.logger.info("Executing pre_stop_func")
                self.pre_stop_func()
            self.logger.info("Exited by SIG number: %s", signnum)
        except Exception as ex:
            self.logger.warning(f"Exited with exception: {ex}")
        finally:
            self.logger.info("Exit shutdown")
