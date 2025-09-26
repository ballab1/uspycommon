#!/usr/bin/env python3

from inspect import CORO_RUNNING
from kubernetes import client, config

# Configs can be set in Configuration class directly or using helper utility
config.load_kube_config()

v1 = client.CoreV1Api()
print("Listing pods which have not succeeded")
ret = v1.list_namespace()
for i in ret.items:
    if "drp" in i.metadata.name or "techops" in i.metadata.name:
        try:
            podlist = v1.list_namespaced_pod(i.metadata.name)
            for pod in podlist.items:
                if pod.status.phase == "Running" or pod.status.phase == "Succeeded":
                    continue
                print(
                    "ns=%s, pod=%s, state=%s"
                    % (i.metadata.name, pod.metadata.name, pod.status.phase)
                )
        except Exception as e:
            if e.status != 403:
                raise
