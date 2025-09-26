#!/usr/bin/env python3

import os
import sys
import copy
import json
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest.mock import Mock, patch
import yaml
import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from drpbase import constant
from drpbase import jobmanager
from kubernetes.client.rest import ApiException


class Obj(object):
    def __init__(self, dict_):
        self.__dict__.update(dict_)


@pytest.fixture
def api_response():
    response = {
        "metadata": {
            "resource_version": "123456",
        },
        "items": [
            {
                "metadata": {
                    "creation_timestamp": "2023-01-21T03:27:42+00:00",
                    "generate_name": "job2-",
                    "labels": {
                        "spawnedby": "jm-myuS-mytopic-drp-staging",
                        "DRP-ID": "PR-1",
                    },
                    "name": "job2-nhmf2",
                    "namespace": "drp-staging",
                    "resource_version": "123456",
                },
                "spec": {"imagePullPolicy": "Always"},
                "status": {
                    "active": 0,
                    "completion_time": "2023-01-21T02:27:55+00:00",
                    "conditions": [
                        {
                            "last_probe_time": "2023-01-21T03:27:56+00:00",
                            "last_transition_time": "2023-01-21T01:27:57+00:00",
                            "message": "",
                            "reason": "DeadlineExceeded",
                            "status": "True",
                            "type": "Failed",
                        }
                    ],
                    "failed": 0,
                    "start_time": "2023-01-21T03:27:43+00:00",
                    "succeeded": 1,
                    "uncounted_terminated_pods": "",
                },
            }
        ],
    }

    time_format = "%Y-%m-%dT%H:%M:%S%z"
    api_response = json.loads(json.dumps(response), object_hook=Obj)

    start_time = datetime.strptime(
        api_response.items[0].status.start_time, time_format
    ).astimezone(timezone.utc)
    api_response.items[0].status.start_time = start_time

    completion_time = datetime.strptime(
        api_response.items[0].status.completion_time, time_format
    ).astimezone(timezone.utc)
    api_response.items[0].status.completion_time = completion_time

    last_transition_time = datetime.strptime(
        api_response.items[0].status.conditions[0].last_transition_time, time_format
    ).astimezone(timezone.utc)
    api_response.items[0].status.conditions[
        0
    ].last_transition_time = last_transition_time

    api_response.items[0].metadata.labels = {
        "spawnedby": "jm-myuS-mytopic-drp-staging",
        "DRP-ID": "PR-1",
    }

    return api_response


@pytest.fixture
def config_dict():
    constant.MAX_ATTEMPTS = 1
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    return cfg["jobmanager"]


@pytest.fixture
def job_manager(config_dict, mocker):
    constant.JOB_MANAGER_NAME = config_dict["job_manager_name"]
    constant.KEEPING_FAILED_JOB_TIME = config_dict["keeping_failed_job_time"]
    constant.KEEPING_SUCCEEDED_JOB_TIME = config_dict["keeping_succeeded_job_time"]
    constant.DEV_NAMESPACE = config_dict["dev_namespace"]
    constant.JOB_MAX_RUNNING_TIME = config_dict["job_max_running_time"]
    constant.MAX_PARALLEL_JOB = config_dict["max_parallel_job"]

    mocker.patch("drpbase.jobmanager.config")
    mocker.patch("drpbase.jobmanager.client.BatchV1Api")
    mocker.patch(
        "drpbase.jobmanager.JobManager._get_current_namespace",
        return_value=constant.DEV_NAMESPACE,
    )
    return jobmanager.JobManager(config_dict["jobs"])


def test_job_creation(job_manager, mocker, caplog):
    job_manager.create_job(
        "job1-",
        job_id="PR-1",
        user_specified_job_name="pr1",
        containers=[{"name": "container1", "args": ["0", "8"]}],
    )
    job_manager.create_job(
        "job2-",
        job_id="PR-2",
        containers=[{"name": "container1", "args": ["5"]}],
        labels={"mylabel2": "mylabel2", "mylabel3": "mylabel3"},
        pod_labels={"mylabel2": "mylabel2", "mylabel3": "mylabel3"},
    )

    with pytest.raises(ValueError):
        job_manager.create_job(
            "job2-", containers=[{"name": "container1", "args": ["0", "8"]}]
        )
    assert "Job id must be specified" in caplog.text

    mocker.patch.object(
        job_manager._batch_v1_api, "create_namespaced_job", side_effect=Exception
    )
    with pytest.raises(Exception):
        job_manager.create_job(
            "job2-",
            job_id="PR-1",
            containers=[{"name": "container1", "args": ["0", "8"]}],
        )
    assert "API fails to create job" in caplog.text


def test_delete_job(job_manager, mocker, api_response, caplog):

    mocker.patch.object(job_manager._batch_v1_api, "list_namespaced_job")
    job_manager.delete_job("PR-1")

    mocker.patch.object(
        job_manager._batch_v1_api, "list_namespaced_job", side_effect=ApiException
    )
    with pytest.raises(ApiException):
        job_manager.delete_job("PR-1")
    assert "Failed to delete Job" in caplog.text

    mocker.patch.object(
        job_manager._batch_v1_api, "list_namespaced_job", side_effect=Exception
    )
    with pytest.raises(Exception):
        job_manager.delete_job("PR-1")
    assert "Failed to delete Job" in caplog.text

    api_response.items[0].status.active = 1
    mocker.patch.object(
        job_manager._batch_v1_api, "list_namespaced_job", return_value=api_response
    )
    mocker.patch.object(job_manager._batch_v1_api, "delete_namespaced_job")
    job_manager.delete_job("PR-1")

    mocker.patch.object(
        job_manager._batch_v1_api, "delete_namespaced_job", side_effect=ApiException
    )
    job_manager.delete_job("PR-1")
    assert "Failed to delete Job id=PR-1" in caplog.text

    mocker.patch.object(
        job_manager._batch_v1_api, "delete_namespaced_job", side_effect=Exception
    )
    job_manager.delete_job("PR-1")
    assert "Failed to delete Job id=PR-1" in caplog.text


def test_monitor_jobs(job_manager, mocker, api_response, caplog):
    mocker.patch.object(job_manager._batch_v1_api, "patch_namespaced_job")

    # An active job cannot be patched
    active_job_response = copy.deepcopy(api_response)
    active_job_response.items[0].status.active = 1
    mocker.patch.object(
        job_manager._batch_v1_api,
        "list_namespaced_job",
        return_value=active_job_response,
    )
    job_manager._monitor_jobs()
    # job should be in cache
    assert job_manager.get_running_job("PR-1") == active_job_response.items[0]
    assert job_manager._batch_v1_api.patch_namespaced_job.call_count == 0

    # Test events
    fake_events = [
        {"type": "ADDED", "object": active_job_response.items[0]},
        {"type": "MODIFIED", "object": api_response.items[0]},
    ]

    mocker.patch("drpbase.jobmanager.watch.Watch.stream", return_value=fake_events)

    job_manager._monitor_jobs()
    # Expect modified job to be patched
    assert job_manager._batch_v1_api.patch_namespaced_job.call_count == 1


def test_monitor_jobs_exception(job_manager, mocker, caplog):
    mocker.patch.object(
        job_manager._batch_v1_api, "list_namespaced_job", side_effect=ApiException
    )
    job_manager._monitor_jobs()
    assert f"Kubernetes API fails in namespace {constant.DEV_NAMESPACE}" in caplog.text

    mocker.patch.object(
        job_manager._batch_v1_api, "list_namespaced_job", side_effect=Exception
    )
    job_manager._monitor_jobs()
    assert (
        f"Failed to monitor jobs in namespace {constant.DEV_NAMESPACE}" in caplog.text
    )


def test_wrong_config(config_dict):
    config = copy.deepcopy(config_dict)

    config["jobs"][0]["spec"]["template"]["spec"].pop("restartPolicy", None)
    jobmanager.JobManager(config["jobs"])

    config["jobs"][0]["metadata"].pop("generateName", None)
    with pytest.raises(ValueError):
        jobmanager.JobManager(config["jobs"])

    config.pop("dev_namespace", None)
    constant.DEV_NAMESPACE = None
    with pytest.raises(ValueError):
        jobmanager.JobManager(config["jobs"])

    constant.DEV_NAMESPACE = config_dict["dev_namespace"]


def test_append_labels(config_dict, job_manager):
    with pytest.raises(ValueError):
        job_manager._append_labels(config_dict["jobs"][1], labels="mylabel")

    config_dict["jobs"][1].pop("metadata")
    with pytest.raises(AttributeError):
        job_manager._append_labels(
            config_dict["jobs"][1], labels={"mylabel": "mylabel"}
        )


def test_update_container_spec(config_dict, job_manager):
    with pytest.raises(ValueError):
        job_manager._update_container_spec(
            config_dict["jobs"][0], {"name": "", "args": ["0", "8"]}
        )

    # if input image string is empty, use default image
    job_manager._update_container_spec(
        config_dict["jobs"][0],
        {"name": "container1", "image": "", "args": ["0", "8"]},
    )
    assert (
        config_dict["jobs"][0]["spec"]["template"]["spec"]["containers"][0]["image"]
        == "s2.ubuntu.home:5000/alpine/simple_job:v1"
    )

    job_manager._update_container_spec(
        config_dict["jobs"][0],
        {
            "name": "container1",
            "image": "my_image",
            "command": ["python3", "--version"],
            "args": ["0", "8"],
        },
    )
    assert (
        config_dict["jobs"][0]["spec"]["template"]["spec"]["containers"][0]["image"]
        == "my_image"
    )

    assert config_dict["jobs"][0]["spec"]["template"]["spec"]["containers"][0][
        "command"
    ] == ["python3", "--version"]

    job_manager._update_container_spec(
        config_dict["jobs"][0], {"name": "container2", "args": ["echo hello"]}
    )
    assert config_dict["jobs"][0]["spec"]["template"]["spec"]["initContainers"][0][
        "args"
    ] == ["echo hello"]

    # KeyError is raised if container image is not found
    config_dict["jobs"][0]["spec"]["template"]["spec"]["containers"][0].pop("image")
    with pytest.raises(KeyError):
        job_manager._update_container_spec(
            config_dict["jobs"][0],
            {"name": "container1", "args": ["0", "8"]},
        )

    config_dict["jobs"][0]["spec"]["template"]["spec"].pop("containers")
    with pytest.raises(KeyError):
        job_manager._update_container_spec(
            config_dict["jobs"][0],
            {"name": "container1", "args": ["0", "8"]},
        )


def test_get_current_namespace(job_manager):
    namespace = job_manager._get_current_namespace()
    assert namespace == constant.DEV_NAMESPACE


def test_get_selector_string(job_manager):
    selector = job_manager._get_selector_string({"key1": "value1", "key2": "value2"})
    assert "key1=value1,key2=value2" == selector


def test_get_running_job(job_manager, api_response):
    job_manager.cache_active_jobs["PR-1"] = api_response.items[0]
    assert 1 == job_manager.get_active_job_count()

    assert api_response.items[0] == job_manager.get_running_job("PR-1")
    assert None is job_manager.get_running_job("PR-2")


def test_get_job_complete_time(job_manager, api_response, caplog):
    caplog.set_level(logging.INFO)
    assert datetime(
        2023, 1, 21, 2, 27, 55, tzinfo=timezone.utc
    ) == job_manager._get_job_complete_time(api_response.items[0])

    api_response.items[0].status.completion_time = None
    assert datetime(
        2023, 1, 21, 1, 27, 57, tzinfo=timezone.utc
    ) == job_manager._get_job_complete_time(api_response.items[0])
    assert "Use condition last_transition_time instead" in caplog.text
    assert "It has been terminated by Kubernetes" in caplog.text

    api_response.items[0].status.conditions[0].type = "Complete"
    assert datetime(
        2023, 1, 21, 1, 27, 57, tzinfo=timezone.utc
    ) == job_manager._get_job_complete_time(api_response.items[0])
    assert "Use condition last_transition_time instead" in caplog.text


def test_patch_job(job_manager, api_response, mocker, caplog):
    caplog.set_level(logging.INFO)
    mocker.patch.object(job_manager._batch_v1_api, "patch_namespaced_job")
    mocker.patch.object(
        job_manager,
        "_get_job_complete_time",
        return_value=(datetime.now(timezone.utc) - timedelta(seconds=10)),
    )
    new_job = copy.deepcopy(api_response.items[0])
    job_manager._patch_job(new_job)
    job_manager._batch_v1_api.patch_namespaced_job.assert_called_with(
        name="job2-nhmf2", namespace=constant.DEV_NAMESPACE, body=new_job
    )

    mocker.patch.object(
        job_manager,
        "_get_job_complete_time",
        return_value=(datetime.now(timezone.utc) - timedelta(seconds=600)),
    )
    new_job = copy.deepcopy(api_response.items[0])
    job_manager._patch_job(new_job)
    assert 0 == new_job.spec.ttl_seconds_after_finished

    failed_job = copy.deepcopy(api_response.items[0])
    failed_job.status.failed = 1
    failed_job.status.succeeded = 0
    mocker.patch.object(
        job_manager,
        "_get_job_complete_time",
        return_value=(datetime.now(timezone.utc) - timedelta(seconds=10)),
    )
    job_manager._patch_job(failed_job)
    job_manager._batch_v1_api.patch_namespaced_job.assert_called_with(
        name="job2-nhmf2", namespace=constant.DEV_NAMESPACE, body=failed_job
    )

    failed_job = copy.deepcopy(api_response.items[0])
    failed_job.status.failed = 1
    failed_job.status.succeeded = 0
    mocker.patch.object(
        job_manager,
        "_get_job_complete_time",
        return_value=(datetime.now(timezone.utc) - timedelta(seconds=600)),
    )
    job_manager._patch_job(failed_job)
    assert 0 == failed_job.spec.ttl_seconds_after_finished

    assert job_manager._batch_v1_api.patch_namespaced_job.call_count == 4

    active_job = copy.deepcopy(api_response.items[0])
    active_job.status.active = 1
    active_job.status.failed = 0
    active_job.status.succeeded = 0
    job_manager._patch_job(active_job)
    # patch_namespaced_job isn't called when job is still active
    assert job_manager._batch_v1_api.patch_namespaced_job.call_count == 4

    job_copy = copy.deepcopy(api_response.items[0])
    mocker.patch.object(
        job_manager._batch_v1_api, "patch_namespaced_job", side_effect=ApiException
    )
    with pytest.raises(ApiException):
        job_manager._patch_job(api_response.items[0])

    assert "Failed to patch Job id=PR-1" in caplog.text

    mocker.patch.object(
        job_manager._batch_v1_api, "patch_namespaced_job", side_effect=Exception
    )
    with pytest.raises(Exception):
        job_manager._patch_job(job_copy)

    assert "Failed to patch Job id=PR-1" in caplog.text


def test_handle_call_backs(job_manager, api_response):
    # Create a mock job
    job = api_response.items[0]
    # Create a mock callback function
    callback = Mock()

    # Create a JobManager instance with the mock callback function
    constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = callback

    # Test that the callback function is called when the job is in call_back_on_jobs
    job_manager._handle_call_backs(constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS, job)
    callback.assert_called_once_with(job)

    # Test that the callback function is not called when the job is not in call_back_on_jobs
    callback.reset_mock()
    constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = None
    job_manager._handle_call_backs(constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS, job)
    callback.assert_not_called()

    # Test that an exception from the callback function is logged
    callback.side_effect = Exception("Test exception")
    constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = callback
    with patch.object(job_manager.logger, "error") as mock_logger:
        job_manager._handle_call_backs(constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS, job)
        assert mock_logger.call_count == 1


def test_call_backs_job_result(job_manager, api_response, mocker):
    mock_handle_job_result_failure = Mock()
    mock_handle_job_result_success = Mock()
    labels = {"DRP-ID": "PR-1"}
    mocker.patch("drpbase.jobmanager.JobManager._patch_job")
    mocker.patch("drpbase.jobmanager.JobManager._watch_jobs")

    # Mock the stream method on the Watch object

    api_version = {
        "api_version": "batch/v1",
        "kind": "Job",
        "metadata": {
            "generate_name": "job-techops-drp-env-job-2-pr-scan-",
            "labels": {"DRP-ID": "PR-1"},
            "name": "job-techops-drp-env-job-2-pr-scan-gcn6q",
            "namespace": "drp-test-jobjob-190",
        },
        "spec": {
            "active_deadline_seconds": 3600,
            "backoff_limit": 3,
            "completion_mode": "NonIndexed",
            "completions": 1,
            "ttl_seconds_after_finished": 60,
        },
        "status": {
            "active": 0,
            "failed": 3,
            "succeeded": None,
        },
    }

    mock_stream = {
        "type": "MODIFIED",
        "object": json.loads(json.dumps(api_version), object_hook=Obj),
    }
    mock_stream["object"].metadata.labels = labels

    with patch("kubernetes.watch.Watch") as mock_watch:
        mocker.patch(
            "drpbase.jobmanager.JobManager.create_job",
            return_value=mock_stream["object"],
        )
        job = job_manager.create_job(
            "job-techops-drp-env-job-2-pr-scan-",
            job_id="PR-1",
            containers=[{"name": "container1", "args": ["5"]}],
            labels=labels,
            pod_labels=labels,
            call_back_on_job=mock_handle_job_result_failure,
        )

        assert job.metadata.name == "job-techops-drp-env-job-2-pr-scan-gcn6q"
        # Create a mock stream

        # Set the mock stream as the return value of the stream method
        mock_watch.return_value.stream.return_value = [mock_stream]
        # An active job cannot be patched
        active_job_response = copy.deepcopy(api_response)
        active_job_response.items[0].status.active = 1
        mocker.patch.object(
            job_manager._batch_v1_api,
            "list_namespaced_job",
            return_value=active_job_response,
        )
        # Create mock callback function
        constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = mock_handle_job_result_failure
        mock_stream["object"].status.failed = 3
        job_manager._monitor_jobs()
        mock_handle_job_result_failure.assert_called_once_with(mock_stream["object"])

        # Set the mock stream as the return value of the stream method
        mock_watch.return_value.stream.return_value = [mock_stream]
        # job has succeeded, it is not retrying
        mock_stream["object"].status.succeeded = 1
        constant.ONE_CALL_BACK_METHOD_FOR_ALL_JOBS = mock_handle_job_result_success
        job_manager._monitor_jobs()
        mock_handle_job_result_success.assert_called_once_with(mock_stream["object"])
