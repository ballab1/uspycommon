#!/usr/bin/env python3
################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import os
import sys
import socket
import pytest
import tempfile

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from drpbase import constant
from drpbase import framework
from drpbase.utils import Utils


@pytest.fixture
def config_framework():
    configdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    # Create a framework passing it the configuration directory name to overwrite the default value,
    # where after deployment in K8s, the configuration files will be located.
    framework.UsFramework().create(configdir)


def test_attempt():
    call = [0]

    @Utils.attempt(attempts=2, interval=0)
    def raise_exception():
        call[0] += 1
        raise Exception

    with pytest.raises(Exception):
        raise_exception()

    assert call[0] == 2


def test_attempt_no_arguments():
    constant.ATTEMPT_INTERVAL = 1
    call = [0]

    @Utils.attempt()
    def raise_exception():
        call[0] += 1
        raise Exception

    with pytest.raises(Exception):
        raise_exception()

    assert call[0] == constant.MAX_ATTEMPTS


def test_attempt_wrong_exception():
    call = [0]

    @Utils.attempt(exceptions=ValueError)
    def raise_exception():
        call[0] += 1
        raise Exception

    with pytest.raises(Exception):
        raise_exception()

    # Although constant.MAX_ATTEMPTS =3, function is called only once.
    # Another attempt won't start due to wrong exception.
    assert call[0] == 1


def test_get_config_value():
    config = {
        "key1": "",
        "key2": ["value21", "value22"],
        "key3": ["value31", ""],
        "key4": "value4",
    }

    val = Utils.get_config_value(config, "key0")
    assert val is None

    with pytest.raises(ValueError, match="Value of key: key0 not found"):
        Utils.get_config_value(config, "key0", is_required=True)

    with pytest.raises(ValueError, match="Value of key: key1 cannot be empty"):
        Utils.get_config_value(config, "key1")

    with pytest.raises(ValueError, match="Value of key: key4 isn't a List"):
        Utils.get_config_value(config, "key4", is_list=True)

    val = Utils.get_config_value(config, "key2", is_list=True)
    assert val == ["value21", "value22"]

    with pytest.raises(
        ValueError, match="Value of key: key3 cannot contain empty value in List"
    ):
        Utils.get_config_value(config, "key3", is_list=True)

    val = Utils.get_config_value(config, "key4", is_required=True)
    assert val == "value4"


def test_check_servers(mocker):
    server = "server1:9092"
    mocked_connection = mocker.patch("drpbase.utils.socket.create_connection")
    results = Utils.check_servers([server])
    assert True is results["server1"]

    mocked_connection.side_effect = ConnectionRefusedError
    results = Utils.check_servers([server])
    assert False is results["server1"]

    mocked_connection.side_effect = socket.timeout
    results = Utils.check_servers([server])
    assert False is results["server1"]


def test_get_secret():
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(b"mysecret")
        fp.seek(0)

        secret_key = os.path.basename(fp.name)
        mount_path = os.path.dirname(fp.name)

        secret = Utils.get_secret(secret_key, mount_path, 1)
        assert "mysecret" == secret

    # test certificate
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as fp:
        cert = """-----BEGIN RSA PRIVATE KEY-----
        XXXXXX
        -----END RSA PRIVATE KEY-----"""
        fp.write(cert)
        fp.seek(0)

        secret_key = os.path.basename(fp.name)
        mount_path = os.path.dirname(fp.name)

        secret = Utils.get_secret(secret_key, mount_path, 1)
        assert cert == secret

    secret = Utils.get_secret("key_not_found", mount_path)
    assert None is secret
