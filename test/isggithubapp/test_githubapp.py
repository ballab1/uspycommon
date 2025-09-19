import os
import yaml
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime
from drpbase import constant, githubappinstances
import jwt
from isggithubapp.checkrun import CheckRun


@pytest.fixture
def config_dict():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    return cfg


@pytest.fixture
def app_dict(config_dict, mocker):
    mock_private_key = "test private key"
    mocker.patch("drpbase.utils.Utils.get_secret", return_value=mock_private_key)
    githubappinstances.GithubAppInstances(config_dict["github_app"])
    return constant.GITHUB_APPS


@pytest.fixture
def github_app_obj(app_dict):
    return app_dict["drpchecker"]


def test_github_app_instance(app_dict, mocker):
    assert app_dict["testapp"].app_identifier == 199
    assert app_dict["drpchecker"].app_identifier == 99


def test_generate_access_token(github_app_obj):
    repo_name = "test_org/test_repo"
    test_token = "test_token"
    with patch.object(jwt, "encode", return_value="test_token"):
        with patch.object(github_app_obj, "client") as mock_client:
            mock_client.request_retry.side_effect = [
                MagicMock(status_code=200, text='{"id": "1"}'),
                MagicMock(status_code=200, json=lambda: {"token": "test_token"}),
            ]
            assert github_app_obj._generate_access_token(repo_name) == test_token


#  create unit test for function _generate_check_run_request
def test_generate_check_run_request(github_app_obj):
    name = "test"
    head_sha = "test"
    details_url = "https://test.com"
    external_id = "test"
    status = "test"
    started_at = datetime.utcnow()
    conclusion = "test"
    completed_at = datetime.utcnow()
    output = {"title": "test"}
    actions = [{"label": "test"}]
    post_parameters = github_app_obj._generate_check_run_request(
        name,
        head_sha,
        details_url,
        external_id,
        status,
        started_at,
        conclusion,
        completed_at,
        output,
        actions,
    )
    assert post_parameters["name"] == name
    assert post_parameters["head_sha"] == head_sha
    assert post_parameters["details_url"] == details_url
    assert post_parameters["external_id"] == external_id
    assert post_parameters["status"] == status
    assert post_parameters["started_at"] == started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert post_parameters["conclusion"] == conclusion
    assert post_parameters["completed_at"] == completed_at.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert post_parameters["output"] == output
    assert post_parameters["actions"] == actions


def test_send_check_run_request(github_app_obj):
    with patch.object(
        github_app_obj, "get_access_token_for_check", return_value="test_access_token"
    ), patch.object(github_app_obj, "client") as mock_client:
        mock_client.request_retry.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": "ok"}),
        ]

        assert github_app_obj.send_check_run_request(
            "post", "test_org", "test_url", {"params1": "value1"}
        ) == {"result": "ok"}


def test_get_access_token_for_check(github_app_obj):
    assert len(github_app_obj.app_token_dict) == 0
    with patch.object(
        github_app_obj, "_generate_access_token", return_value="test_access_token"
    ):
        assert (
            github_app_obj.get_access_token_for_check("test_org/test_repo")
            == "test_access_token"
        )
    # Using cache
    assert len(github_app_obj.app_token_dict) == 1
    assert (
        github_app_obj.get_access_token_for_check("test_org/test_repo")
        == "test_access_token"
    )


def test_update_check_run(github_app_obj):
    check_run = CheckRun({}, github_app_obj)
    check_run.url = (
        "https://eos2git.cec.lab.emc.com/api/v3/repos/org_name/repo_name/check-runs/1"
    )
    with patch.object(
        github_app_obj, "get_access_token_for_check", return_value="test_access_token"
    ):
        mock_response = {"id": "1"}
        with patch.object(
            github_app_obj, "send_check_run_request", return_value=mock_response
        ):
            check_run.update()
            assert check_run.id == "1"
