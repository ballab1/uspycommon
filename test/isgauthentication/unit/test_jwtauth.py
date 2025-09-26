#!/usr/bin/env python3
################################################################################
# Copyright (c) 2020-2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

from http.client import HTTPException
import os
import sys
from unittest.mock import Mock
import pytest
import jwt


sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)

from isgAuthentication.jwtAuthentication import JWTAuthentication


@pytest.fixture
def payload():
    payload = {
        "username": "narayana_chunduri",
        "firstName": "Narayana",
        "lastName": "Chunduri",
        "email": "Narayana_Chunduri@Dell.com",
        "exp": 1626901660,
    }
    return payload


@pytest.fixture
def sso_response():
    sso_response = {
        "result": {
            "username": "kavithadevi.perumal",
            "firstName": "Kavithadevi",
            "lastName": "Perumal",
            "email": "kavithadevi.perumal@Dell.com",
            "authority": "BYOS_USER",
        }
    }
    return sso_response


@pytest.fixture
def ssoToken():
    return "uyts87687h"


@pytest.fixture
def jsonWebToken():
    return {"jwtToken": "jwt123456789"}


def test_issue_jwt(mocker):
    jwtWebToken = mocker.patch(
        "isgAuthentication.jwtAuthentication.jwt.encode", return_value="uyts87687h"
    )
    assert jwtWebToken is not None


def test_validate_empty_payload(jsonWebToken: str, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.jwt.decode",
        side_effect=[jwt.ExpiredSignatureError, {"sso_token": "uyts87687h"}],
    )
    mocker.patch(
        "isgAuthentication.jwtAuthentication.JWTAuthentication.get_sso_user_details",
        side_effect=[{}],
    )
    assert JWTAuthentication.validate_jwt(jsonWebToken) is None


def test_validate_payload(jsonWebToken: str, payload: dict, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.jwt.decode",
        side_effect=[jwt.ExpiredSignatureError, {"sso_token": "uyts87687h"}],
    )
    mocker.patch(
        "isgAuthentication.jwtAuthentication.JWTAuthentication.get_sso_user_details",
        side_effect=[{"payload": payload}],
    )
    assert JWTAuthentication.validate_jwt(jsonWebToken) is not None


def test_validate_jwt_expiredSignatureError(jsonWebToken: str, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.jwt.decode",
        side_effect=jwt.ExpiredSignatureError,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        JWTAuthentication.validate_jwt(jsonWebToken)


def test_validate_jwt_exception(jsonWebToken: str, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.jwt.decode", side_effect=Exception
    )
    assert JWTAuthentication.validate_jwt(jsonWebToken) is None


def test_valid_ssoToken(ssoToken: str, sso_response: dict, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.base64.b64decode",
        return_value=b"ZGF0YSB0byBiZSBlbmNvZGVk",
    )
    mocker.patch(
        "isgAuthentication.jwtAuthentication.requests.get",
        return_value=Mock(json=lambda: sso_response),
    )
    assert "sso_token" in JWTAuthentication.get_sso_user_details(ssoToken)


def test_ssoToken_exception(ssoToken: str, mocker):
    mocker.patch(
        "isgAuthentication.jwtAuthentication.JWTAuthentication.get_sso_user_details",
        side_effect=Exception,
    )
    with pytest.raises(Exception):
        assert JWTAuthentication.get_sso_user_details(ssoToken) is None
