#!/usr/bin/env python3
################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import sys
import pytest
import yaml

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)

from drpbase.statusreporter import StatusReporter
from datetime import datetime
import json
from drpbase import constant
from drpbase import framework
from isgkafka.producer import KProducer
from drpbase.producers import KProducers

PRODUCER = "isgkafka.producer.Producer"


@pytest.fixture(name="config_dict")
def fixture_config_dict():
    constant.MAX_ATTEMPTS = 1
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r", encoding="utf8") as yaml_file:
        cfg = yaml.safe_load(yaml_file)

    producer_cfg = cfg["kafka"].get("producers", None)[0]
    producer_cfg["bootstrap_servers"] = cfg["kafka"].get("bootstrap_servers", None)
    constant.KAFKA_VALIDATION_TIMEOUT = 1.0

    return cfg


@pytest.fixture(name="init_producers")
def fixture_init_producers(config_dict, mocker):
    mocker.patch(PRODUCER)
    constant.KAFKA_VALIDATION_TIMEOUT = 1.0
    constant.PRODUCERS = KProducers(config_dict["kafka"])
    return constant.PRODUCERS


@pytest.fixture
def aggregator_report(config_dict, init_producers):
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    cfg = None
    with open(cfg_file, "r", encoding="utf8") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    return StatusReporter(cfg["status_reporter"])


def test_check_run_payload(aggregator_report):
    check_run_name = "test check_run_name"
    head_sha = "abcabcabc"
    status = "in_progress"
    title = "test title"
    summary = "test summary"
    text = "test text"
    details_url = "https://test.com"
    external_id = "123"
    conclusion = None
    started_at = datetime.utcnow()
    completed_at = datetime.utcnow()
    actions = [{"label": "test"}]

    check_run_payload = aggregator_report.generate_check_run_payload(
        check_run_name=check_run_name,
        head_sha=head_sha,
        status=status,
        title=title,
        summary=summary,
        text=text,
        details_url=details_url,
        external_id=external_id,
        conclusion=conclusion,
        started_at=started_at,
        completed_at=completed_at,
        actions=actions,
    )
    print(json.dumps(check_run_payload, indent=4))

    report = aggregator_report.generate_report(
        org_name="test_org",
        repo_name="test_repo",
        event_source_type="github",
        request_id="test_request_id",
        request_timestamp="test_requset_timestamp",
        reply_source="trufflehog",
        check_run_payload=check_run_payload,
    )
    print(json.dumps(report, indent=4))
    assert check_run_payload["name"] == check_run_name
    assert check_run_payload["head_sha"] == head_sha
    assert check_run_payload["status"] == status
    assert check_run_payload["output"]["title"] == title
    assert check_run_payload["output"]["summary"] == summary
    assert check_run_payload["output"]["text"] == text
    assert check_run_payload["details_url"] == details_url
    assert check_run_payload["external_id"] == external_id
    assert check_run_payload.get("conclusion", None) is None
    assert check_run_payload["started_at"] == started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert check_run_payload["completed_at"] == completed_at.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert check_run_payload["actions"] == actions
