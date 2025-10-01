################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import logging
import copy
import threading
from datetime import datetime
from datetime import timezone
from typing import List
from kubernetes import client
from kubernetes import config
from kubernetes import watch
from kubernetes.client import V1Job
from kubernetes.client.rest import ApiException
from drpbase import constant
from drpbase.utils import Utils


class JobManager:
    """
    JobManager class
    """

    ID_KEY = "DRP-ID"

    def __init__(self, job_config):
        """
            Create a job manager instance

        Args:
            job_config (dict): job configuration_
            mode (str, optional): running mode. Defaults to "k8s".
        Raises:
            ValueError: A namespace needs to be defined for job manager
            ValueError: generateName field is required under job metadata
        """
        self.logger = logging.getLogger(constant.LOGGER_NAME)
        self._k8s = True  # job manager running in k8s

        self.ns = self._get_current_namespace()

        if self.ns is None:
            raise ValueError("A namespace needs to be defined for job manager")

        if self._k8s:
            config.load_incluster_config()
        else:
            config.load_kube_config()

        self._batch_v1_api = client.BatchV1Api()

        self._label = {}
        label_key = "spawnedby"
        # each job will have a label, unique to the jobs spawned by this job manager
        self._label[label_key] = constant.JOB_MANAGER_NAME + "-" + self.ns

        # a dictionary to hold the job config loaded from configuration
        self._job_configs = {}

        # holds the job objects created by this job manager
        self.spawned_jobs = {}

        # The dictionary of active jobs only, spawned by the jobmanager.
        self.cache_active_jobs = {}

        self._lock = threading.Lock()

        for job in job_config:
            # If user has not specified maximum running time in the job config, set it to default value
            if job["spec"].get("activeDeadlineSeconds", None) is None:
                job["spec"]["activeDeadlineSeconds"] = constant.JOB_MAX_RUNNING_TIME

            # Set default value of restartPolicy and backoffLimit if not defined in config
            if job["spec"]["template"]["spec"].get("restartPolicy", None) is None:
                self.logger.info("Pod restart policy not specified. Set to Never")
                job["spec"]["template"]["spec"]["restartPolicy"] = "Never"

            if job["spec"].get("backoffLimit", None) is None:
                self.logger.info("Job backoffLimit not specified. Set to 0")
                job["spec"]["backoffLimit"] = 0

            if job["metadata"].get("generateName", None) is None:
                raise ValueError("generateName field is required under job metadata")

            self._job_configs[job["metadata"]["generateName"]] = job
            self._append_labels(job, self._label)

        self._thrd_name = "jobmanager-" + constant.JOB_MANAGER_NAME + "-" + self.ns

    def start(self):
        """
        A thread that monitors job executions
        """
        self.logger.info("Starting jobmanager watch in thread %s", self._thrd_name)
        thrd = threading.Thread(
            target=self._watch_jobs, name=self._thrd_name, daemon=True
        )
        thrd.start()

    def _append_labels(self, job_config, labels, pod_labels=None):
        """
            Append labels to existing labels of a job

        Args:
            job_config (dict): job configuration
            labels (dict): a dict that contains keys and values for labels
            pod_labels (dict): a dict that contains keys and values for pod labels

        Raises:
            ValueError: label is required to be a dictionary type
            AttributeError: raise exception if key no found
        """
        if labels is None or isinstance(labels, dict) is False:
            raise ValueError("label is required to be a dictionary type.")
        if pod_labels is not None and isinstance(pod_labels, dict) is False:
            raise ValueError("pod_labels is required to be a dictionary type.")
        # job level labels
        try:
            if job_config.get("metadata").get("labels", None):
                job_config.get("metadata").get("labels").update(labels)
            else:
                job_config["metadata"]["labels"] = labels
        except AttributeError as ex:
            self.logger.error(
                "Key metadata not found in job configuration. Exception type: %s, Message: %s",
                ex.__class__.__name__,
                str(ex),
            )
            raise ex

        if pod_labels:
            # pod level labels
            try:
                # Check if "metadata" is in the dictionary
                if "metadata" not in job_config["spec"]["template"]:
                    # If not, add it with an empty dictionary as a value
                    job_config["spec"]["template"]["metadata"] = {}
                # Check if "labels" is in the "metadata" dictionary
                if "labels" not in job_config["spec"]["template"]["metadata"]:
                    # If not, add it with an empty dictionary as a value
                    job_config["spec"]["template"]["metadata"]["labels"] = {}
                job_config["spec"]["template"]["metadata"]["labels"] |= pod_labels
            except AttributeError as ex:
                self.logger.error(
                    "job_config[spec][template][metadata][labels] key metadata not found in job configuration. Exception type: %s, Message: %s",
                    ex.__class__.__name__,
                    str(ex),
                )
                raise ex

    def _update_container_spec(self, job_config, container_spec):
        """
            Update container configuration in job config with the given container spec

        Args:
            job_config (dict): job configuration
            container_spec (dict): a dict that contains keys and values for container spec to be updated.
            The following fields can be updated in container spec - args, command, image
            For args, the value is added to existing args. For command and image, the value is replaced.

        Raises:
            ValueError: Container name is required for job
            KeyError: raise exception if key no found in config
        """
        container_name = container_spec.get("name", None)
        if container_name is None or len(container_name) == 0:
            raise ValueError("Container name is required for job")

        try:
            # search container name in job config and update container spec
            # container name needs to be unique in a jobContainers']
            init_containers = Utils.get_config_value(
                job_config["spec"]["template"]["spec"],
                "initContainers",
                is_list=True,
                default=[],
            )

            for container in (
                job_config["spec"]["template"]["spec"]["containers"] + init_containers
            ):
                if container_name == container.get("name"):
                    command = container_spec.get("command", None)
                    if command is not None and len(command) > 0:
                        container["command"] = command

                    image = container_spec.get("image", None)
                    if image is not None and len(image.strip()) > 0:
                        container["image"] = image.strip()

                    if len(container["image"]) == 0:
                        raise ValueError("Container image is required for job")

                    # If additional args are provided, append them to existing args
                    args = container_spec.get("args", None)
                    if args is not None and len(args) > 0:
                        if container.get("args", None) is None:
                            container["args"] = args
                        else:
                            container["args"] = container["args"] + args
        except KeyError as ex:
            self.logger.error(
                "Cannot update container %s spec. Exception type: %s, Message: %s",
                container_name,
                ex.__class__.__name__,
                str(ex),
            )
            raise ex

    def create_job(
        self,
        job_generate_name: str,
        delete_existing_job: bool = True,
        *,
        user_specified_job_name: str = "",
        job_id: str = None,
        containers: List[dict] = None,
        labels: dict = None,
        pod_labels: dict = None,
    ):
        """
            Create a job in a namespace
        Args:
            job_generate_name (str): Job generateName from configuration. Job name will begin with this name. Required.
            delete_existing_job (bool): Delete an existing job with the same id, if any. Defaults to True.
            user_specified_job_name (str, optional): The supplied value will become part of the job name. Defaults to "".
            job_id (str): label that uniquely identifies a job. Required. Running two jobs with the same id is not recommended.
            containers (List[dict], optional): Arguments to be supplied to the containers of the job -
                {'name': container_name, 'args': ["arg1", "arg2"]}. Defaults to None.
            labels (dict, optional): Labels to be attached to the created Job. Defaults to None.
            pod_labels (dict, optional): Labels to be attached to the created Pod. Defaults to None.

        Raises:
            ValueError: Job id must be specified
            Exception: API fails to create job
        """
        # make sure job id is not empty
        if job_id is None or len(job_id) == 0:
            self.logger.error("Job id must be specified")
            raise ValueError("Job id must be specified")

        containers = {} if containers is None else containers
        labels = {} if labels is None else labels

        error_msg = f"API fails to create job id {job_id} in namespace {self.ns}"
        try:
            if delete_existing_job:
                # delete existing job if any
                self.delete_job(job_id)

            # need a deepcopy of job config to avoid pollution of original job config
            job_config = copy.deepcopy(self._job_configs[job_generate_name])

            # Update generateName string if user_specified_job_name is specified
            # user_specified_job_name is appended to existing generateName string
            if len(user_specified_job_name) > 0:
                job_config["metadata"]["generateName"] = (
                    job_config["metadata"]["generateName"]
                    + user_specified_job_name
                    + "-"
                )

            # Update job container spec
            for container in containers:
                self._update_container_spec(job_config, container)

            # Add job id as a label to the job
            labels[JobManager.ID_KEY] = job_id
            # Update job labels
            self._append_labels(job_config, labels, pod_labels)

            job = self._batch_v1_api.create_namespaced_job(
                body=job_config, namespace=self.ns
            )
            self.logger.info(
                f"Job id {job_id} with name {job.metadata.name} is created in namespace {self.ns}."
            )
            return job
        except Exception as ex:
            log_msg = (
                error_msg
                + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )
            self.logger.error(log_msg)
            raise ex

    def _handle_call_backs(self, call_back_function, job: V1Job):
        """
            Handle call backs for a job
        Args:
            call_back_function (function): a function that handles call backs
            job (V1Job): a k8s job object
        """
        job_name = job.metadata.name
        if call_back_function:
            try:
                if call_back_function:
                    call_back_function(job)
            except Exception as ex:
                self.logger.error(
                    f"Failed to _handle_call_backs job in namespace {self.ns}. "
                    + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
                )
        else:
            self.logger.debug(f"call_back_function not found for Job name={job_name}")

    def _monitor_jobs(self):
        """
        Monitoring job status. Deleting failed or succeeded jobs
        """
        try:
            self.logger.info(
                "Retrieving jobs spawned by this uS, i.e., with labels="
                + f"{self._get_selector_string(self._label)} in namespace {self.ns}"
            )
            api_response = self._batch_v1_api.list_namespaced_job(
                self.ns, label_selector=self._get_selector_string(self._label)
            )
            # set initial resource version
            resource_version = api_response.metadata.resource_version

            tmp_jobs = {}
            for job in api_response.items:
                # We only cache active jobs. We patch finished jobs.
                # Each job has "activeDeadlineSeconds" specified. Therefore, hung jobs will
                # fail after the specified time. We will patch the job after it fails.
                if job.status.active:
                    tmp_jobs[job.metadata.labels[JobManager.ID_KEY]] = job
                    self.logger.debug(
                        f"Job id={job.metadata.labels[JobManager.ID_KEY]} & name={job.metadata.name} is active in namespace {self.ns} and added in cache"
                    )
                # The following function will skip active jobs or jobs that have already been patched
                self._patch_job(job)

            with self._lock:
                self.cache_active_jobs = tmp_jobs

            watcher = watch.Watch()
            stream = watcher.stream(
                self._batch_v1_api.list_namespaced_job,
                self.ns,
                label_selector=self._get_selector_string(self._label),
                resource_version=resource_version,
            )

            for event in stream:
                # check for each single job status
                job = event["object"]
                if event["type"] == "ADDED":
                    self._handle_added_event(job)

                if event["type"] == "MODIFIED":
                    self._handle_modified_event(job)

                if event["type"] == "DELETED":
                    self._handle_deleted_event(job)

        except ApiException as ex:
            # If exception is due to watch timeout, we retry immediately since it is not an error
            # but a feature of K8s API.
            if ex.status == 410:
                self.logger.info("Resource expired.")
            else:
                self.logger.error(
                    f"Kubernetes API fails in namespace {self.ns}. "
                    + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
                )
        except Exception as ex:
            self.logger.error(
                f"Failed to monitor jobs in namespace {self.ns}. "
                + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )

    def _handle_added_event(self, job: V1Job):
        """
            Handle added event by adding job to cache
        Args:
            job (V1Job): k8s job object
        """
        job_id = job.metadata.labels[JobManager.ID_KEY]
        job_name = job.metadata.name

        with self._lock:
            # Check if job id exists in cache and print a warning to enable debugging
            if job_id in self.cache_active_jobs:
                log_msg = (
                    "Active job id="
                    + job_id
                    + " & name="
                    + job_name
                    + " is found in cache. "
                    + "Since we do not add job in the cache during job creation time, "
                    + "it should not exist in cache. Overwriting it."
                )
                self.logger.error(log_msg)
            else:
                self.logger.info(
                    f"Active job id={job_id} & name={job_name} is added to the cache"
                )

            self.cache_active_jobs[job_id] = job

    def _handle_modified_event(self, job: V1Job):
        """
            Function to handle modified event with callback, patch and cache management
        Args:
            job (V1Job): k8s job object
        """
        job_id = job.metadata.labels[JobManager.ID_KEY]
        job_name = job.metadata.name

        if job.status.succeeded or job.status.failed:
            # If restart policy of job is "Never", a new pod will be launched for each failure
            # until backoffLimit is reached. Each newly launched pod will generate a new "MODIFIED" event
            # and increment job.status.failed but keep job.status.active as 1. At the end of retries,
            # job.status.active will be zero and then we execute callback function and patch job.
            # If restart policy of job is "OnFailure", the same pod will be restarted up to backoffLimit
            # if it fails. There is only one "MODIFIED" event for this case. Therefore, we go ahead to
            # execute callback function and patch job.
            # If a job is successful, its job.status.active should be zero.
            # As long as job is active, we don't update the cache. The job will be active under
            # a MODIFIED event (provided no one is patching it), only when restartPolicy
            # is Never & backoffLimit > 0 & the pod failed.
            if job.status.active:
                self.logger.debug(
                    f"Job id={job_id} & name={job_name} failed {job.status.failed}/{job.spec.backoff_limit} times."
                )
                # skip this event if job is still active due to failure try and wait
                return

            if (
                job_id in self.cache_active_jobs
                and constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS
            ):
                self._handle_call_backs(constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS, job)
            # Remove job from cache if it exists
            with self._lock:
                if job_id in self.cache_active_jobs:
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} is in cache. Removing it."
                    )
                    self.cache_active_jobs.pop(job_id)
            self._patch_job(job)
        else:
            self.logger.debug(
                f"Job id={job_id} & name={job_name} has been modified but not completed."
            )

    def _handle_deleted_event(self, job: V1Job):
        """
            Handle deleted event by removing job from cache
        Args:
            job (V1Job): k8s job object
        """
        job_id = job.metadata.labels[JobManager.ID_KEY]
        job_name = job.metadata.name

        # Remove job from cache if it exists
        with self._lock:
            if job_id in self.cache_active_jobs:
                self.logger.error(
                    f"Job id={job_id} & name={job_name} is deleted out of job manager control."
                )
                self.cache_active_jobs.pop(job_id)

    def _watch_jobs(self):
        """
        Monitoring job status.
        """
        # When monitor_job exits, we initiate a new monitor_job
        while True:
            self.logger.info(f"Starting monitoring of jobs in {self.ns} namespace")
            self._monitor_jobs()

    def _get_current_namespace(self):
        """
            Get namespace of current pod

        Returns:
            str: a namespace
        """
        namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        # If in k8s, get namespace from path.
        # If not found, we assume job manager is running in local VM.
        if os.path.exists(namespace_path):
            with open(namespace_path, encoding="utf-8") as f:
                return f.read().strip()

        # return a dev namespace if nothing is found assuming running on local VM
        self._k8s = False
        return constant.DEV_NAMESPACE

    def _get_selector_string(self, selectors):
        """
            Create a selector string from the given dictionary of selectors.

        Args:
            selectors (dict): The selectors to stringify.
        Returns:
            str: The selector string for the given dictionary.
        """
        return ",".join([f"{k}={v}" for k, v in selectors.items()])

    def delete_job(self, job_id: str):
        """
            Delete all jobs having the input job_id.
        Args:
            job_id (str): Job id
        """
        error_msg = f"Failed to delete Job id={job_id} in namespace {self.ns}. "
        try:
            # find existing jobs with same id
            query_labels = copy.deepcopy(self._label)
            query_labels[JobManager.ID_KEY] = job_id
            api_response = self._batch_v1_api.list_namespaced_job(
                self.ns, label_selector=self._get_selector_string(query_labels)
            )

            tmp_jobs = {}
            # Delete existing jobs that have same job_id
            for job in api_response.items:
                try:
                    # Since the cache only holds active jobs, we need to delete only active jobs from the cache
                    if job.status.active:
                        tmp_jobs[job.metadata.labels[JobManager.ID_KEY]] = job

                    self._batch_v1_api.delete_namespaced_job(
                        name=job.metadata.name,
                        namespace=self.ns,
                        body=client.V1DeleteOptions(
                            propagation_policy="Foreground", grace_period_seconds=0
                        ),
                    )
                    self.logger.info(
                        f"Job id={job_id} & name={job.metadata.name} is deleted in namespace {self.ns}"
                    )
                except ApiException as ex:
                    if ex.status == 404 or ex.status == 409:
                        self.logger.info(
                            f"Job id={job_id} & name={job.metadata.name} has already been deleted."
                        )
                    else:
                        log_msg = (
                            error_msg
                            + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
                        )
                        self.logger.error(log_msg)
                except Exception as ex:
                    log_msg = (
                        error_msg
                        + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
                    )
                    self.logger.error(log_msg)

            if len(tmp_jobs) > 1:
                self.logger.error(
                    f"More than one job id={job_id} are found in namespace {self.ns}"
                )

            if len(tmp_jobs):
                with self._lock:
                    for jid in tmp_jobs:
                        if jid in self.cache_active_jobs:
                            self.cache_active_jobs.pop(jid)
                        else:
                            self.logger.error(
                                f"Active job id={jid} is not found in cache"
                            )

        except ApiException as ex:
            log_msg = (
                error_msg
                + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )
            self.logger.error(log_msg)
            raise ex
        except Exception as ex:
            log_msg = (
                error_msg
                + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )
            self.logger.error(log_msg)
            raise ex

    def _patch_job(self, job: V1Job):
        """
            If a job has completed (either failed or succeeded) and not already patched then patch it,
            ignoring active jobs.
        Args:
            job (V1Job): K8s Job object
        """
        try:
            # Check job status
            job_name = job.metadata.name
            job_id = job.metadata.labels[JobManager.ID_KEY]
            time_now = datetime.now(timezone.utc)

            # If ttl_seconds_after_finished is set, we don't want to reset it.
            if (
                hasattr(job.spec, "ttl_seconds_after_finished")
                and job.spec.ttl_seconds_after_finished
            ):
                self.logger.debug(
                    f"Job id={job_id} & name={job_name} has ttl_seconds_after_finished specifed. Not patching."
                )
                return

            if job.status.active:
                self.logger.debug("Job %s is active. Not patching", job_name)
                return

            # Calculate the time delta between now and the time when the job is completed
            delta = int((time_now - self._get_job_complete_time(job)).total_seconds())

            if job.status.failed:
                # job is failed, we will delete it after a while
                if delta < constant.KEEPING_FAILED_JOB_TIME:
                    job.spec.ttl_seconds_after_finished = (
                        constant.KEEPING_FAILED_JOB_TIME - delta
                    )
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} failed. "
                        + f"It will be deleted in {constant.KEEPING_FAILED_JOB_TIME - delta} seconds."
                    )
                else:
                    job.spec.ttl_seconds_after_finished = 0
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} failed. "
                        + "It will be deleted in 0 seconds."
                    )

                self._batch_v1_api.patch_namespaced_job(
                    name=job_name, namespace=self.ns, body=job
                )

            elif job.status.succeeded:
                # job is succeeded, we will delete it after a while
                if delta < constant.KEEPING_SUCCEEDED_JOB_TIME:
                    job.spec.ttl_seconds_after_finished = (
                        constant.KEEPING_SUCCEEDED_JOB_TIME - delta
                    )
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} succeeded. "
                        + f"It will be deleted in {constant.KEEPING_SUCCEEDED_JOB_TIME - delta} seconds."
                    )
                else:
                    job.spec.ttl_seconds_after_finished = 0
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} succeeded. "
                        + "It will be deleted in 0 seconds."
                    )

                self._batch_v1_api.patch_namespaced_job(
                    name=job_name, namespace=self.ns, body=job
                )

            else:
                self.logger.error("Job status is unknown.")

        except ApiException as ex:
            if ex.status == 404 or ex.status == 409:
                self.logger.info(f"Job {job_name} has already been deleted.")
            else:
                error_msg = f"Failed to patch Job id={job_id} & name={job_name} in namespace {self.ns}. "
                log_msg = (
                    error_msg
                    + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
                )
                self.logger.error(log_msg)
                raise ex
        except Exception as ex:
            error_msg = f"Failed to patch Job id={job_id} & name={job_name} in namespace {self.ns}. "
            log_msg = (
                error_msg
                + f"Exception type: {ex.__class__.__name__}, Message: {str(ex)}"
            )
            self.logger.error(log_msg)
            raise ex

    def _get_job_complete_time(self, job: V1Job) -> datetime:
        """
            Get job completion time. If job has no completion time, use condition last_transition_time instead.

        Args:
            job (V1Job): k8s job object

        Returns:
            datetime: job completion time
        """
        job_id = job.metadata.labels[JobManager.ID_KEY]
        job_name = job.metadata.name

        # return now if no completion time is found
        complete_time = datetime.now(timezone.utc)

        if (
            hasattr(job.status, "completion_time")
            and job.status.completion_time is not None
        ):
            return job.status.completion_time

        self.logger.error(
            f"Job id={job_id} & name={job_name} has no completion time. "
            + "Use condition last_transition_time instead."
        )

        if hasattr(job.status, "conditions") and job.status.conditions is not None:
            for condition in job.status.conditions:
                if condition.type == "Complete" and condition.status == "True":
                    complete_time = condition.last_transition_time

                if condition.type == "Failed" and condition.status == "True":
                    complete_time = condition.last_transition_time

                if (
                    condition.reason == "DeadlineExceeded"
                    and condition.status == "True"
                ):
                    self.logger.info(
                        f"Job id={job_id} & name={job_name} was running over {constant.JOB_MAX_RUNNING_TIME} seconds. "
                        + "It has been terminated by Kubernetes"
                    )

        return complete_time

    def get_active_job_count(self) -> int:
        """Get the number of active jobs

        Returns:
            int: number of active jobs
        """
        with self._lock:
            return len(self.cache_active_jobs)

    def get_running_job(self, job_id: str) -> V1Job:
        """
            Get the running job with the given job id
        Args:
            job_id (str): a job id

        Returns:
            (V1Job): a k8s job object
        """
        with self._lock:
            if job_id in self.cache_active_jobs:
                return self.cache_active_jobs[job_id]

            return None
