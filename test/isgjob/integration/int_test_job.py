#!/usr/bin/env python3

import os
from drpbase import constant
from drpbase import framework
from time import sleep


def test_main():
    """
    A test function that creates k8s jobs.
    """

    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)

    # Create jobs

    # Provide container argument as a list of dictionary with the following format.
    # {'name': 'container_name', 'args': [arg1, arg2]}
    constant.JOB_MANAGER.create_job(
        "job1-", job_id="PR1", containers=[{"name": "container1", "args": ["0", "8"]}]
    )

    # Provide labels as dictionary
    constant.JOB_MANAGER.create_job(
        "job1-",
        job_id="PR2",
        containers=[{"name": "container1", "args": ["0", "10"]}],
        labels={"mylabel1": "mylabel1"},
    )

    constant.JOB_MANAGER.create_job(
        "job2-",
        delete_existing_job=False,
        job_id="PR3",
        containers=[
            {
                "name": "container1",
                "args": ["5"],
                "image": "s2.ubuntu.home:5000/docker.io/python:3.9.21-alpine3.20",
                "command": ["python", "--version"],
            }
        ],
        labels={"mylabel2": "mylabel2", "mylabel3": "mylabel3"},
    )

    # Job manager is implemented as a daemon thread, so wait for jobs to complete.
    sleep(80)


if __name__ == "__main__":
    test_main()
