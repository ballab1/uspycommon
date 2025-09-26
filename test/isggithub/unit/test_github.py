################################################################################
# Copyright (c) 2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################

import os
import sys
from unittest.mock import mock_open

import pytest
import time
import yaml

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../src"))
)
from isggithub.github import GitHub

TEST_ORG_NAME = "test_org"
TEST_REPO_NAME = "test_repo"
TEST_COMMIT_SHA = "t1es2t"
TEST_PR_NUMBER = 2
TEST_CHECKER_NAME = "test_checker_name"
TEST_STATUS_PROGRESS = "in_progress"
TEST_STATUS_COMPLETE = "completed"
TEST_DEATAIL_URL = "https://test_url/"
TEST_TITLE = "test title"
TEST_SUMMARY = "testing chechrun status method"
TEST_CONCLUSION = "success"
TEST_ACTION = [{"label": "Rerun", "description": "Run build", "identifier": "RERUN"}]
TEST_DETAILS_TEXT = "test details content"
TEST_CHECKER_RUN_ID = 16453


@pytest.fixture
def config_dict():
    top = os.path.realpath(os.path.join(os.path.dirname(__file__), "config"))
    cfg_file = os.path.abspath(os.path.join(top, "configroot.yaml"))
    with open(cfg_file, "r") as yaml_file:
        cfg = yaml.safe_load(yaml_file)
    return cfg


@pytest.fixture
def init_class(config_dict, mocker):
    mocker.patch("drpbase.utils.Utils.get_secret", return_value="uyts87687h")
    obj = GitHub(config_dict["github"])
    return obj


@pytest.fixture
def project_level_exclusion_dict():
    project_level_exclusion = {
        "project_exclusion_list": {
            "exclusion_file_paths": ["file1.py"],
            "exclusion_folders": ["dirc_a/dirc_b"],
        }
    }
    return project_level_exclusion


@pytest.fixture
def project_level_inclusion_dict():
    project_level_inclusion = {
        "project_inclusion_list": {
            "inclusion_file_paths": ["file1.py"],
            "inclusion_folders": ["dirc_a"],
        }
    }
    return project_level_inclusion


class MockSession:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.links = ""
        self.ok = True
        self.status_code = 200

    def mount(self, url, adapter):
        pass

    def json(self):
        return self.return_value

    def post(self, url, data):
        return self.return_value

    def patch(self, url, data):
        return self.return_value

    def raise_for_status(self):
        pass


def testcheck_request_window(init_class, mocker):
    mock_response_header = {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(time.time() + 3),
    }
    mocker.patch("drpbase.utils.Utils.wait_for")
    res = init_class.client.check_request_window(mock_response_header)
    assert res is None


def test_get_changed_files(init_class, mocker):
    mock_response = [{"filename": "file1.py"}, {"filename": "file2.py"}]
    mock_session_response = MockSession(mock_response)
    mocker.patch("requests.Session.get", return_value=mock_session_response)

    pr_files = init_class._get_changed_files(
        TEST_ORG_NAME, TEST_REPO_NAME, TEST_COMMIT_SHA
    )
    assert pr_files == mock_response


def test_get_project_level_service_config(init_class, mocker):
    mock_session_response = MockSession()
    mock_session_response.text = "test:\n key:\n  - 'value'"

    mocker.patch("requests.Session.get", return_value=mock_session_response)

    raw_url = "https://test/url/"
    pull_files = init_class.get_project_level_service_config(raw_url)
    assert pull_files == {"test": {"key": ["value"]}}


def test_get_pull_request_files_with_download(
    init_class, project_level_inclusion_dict, mocker
):
    mock_response = [{"filename": "file1.py"}, {"filename": "file2.py"}]
    mock_session_response = MockSession(mock_response)
    mock_session_response.text = "print('test')"

    mocker.patch("os.makedirs")
    mocker.patch("shutil.rmtree")
    mocker.patch("os.path.exists")
    mocker.patch("builtins.open", mock_open())

    mocker.patch("os.path.dirname", return_value="test_dir")
    mocker.patch("requests.Session.get", return_value=mock_session_response)
    mocker.patch(
        "isggithub.github.GitHub.get_project_level_service_config",
        return_value=project_level_inclusion_dict,
    )

    pull_files = init_class.get_pull_request_files(
        TEST_ORG_NAME,
        TEST_REPO_NAME,
        TEST_PR_NUMBER,
        TEST_COMMIT_SHA,
        local_workspace_dir="test_dir",
    )
    assert pull_files == [{"filename": "file1.py"}]


def test_get_pull_request_inclusion_files_without_download(
    init_class, project_level_inclusion_dict, mocker
):
    mock_response = [{"filename": "file1.py"}, {"filename": "file2.py"}]
    mock_session_response = MockSession(mock_response)

    mocker.patch("requests.Session.get", return_value=mock_session_response)
    mocker.patch(
        "isggithub.github.GitHub.get_project_level_service_config",
        return_value=project_level_inclusion_dict,
    )

    pull_files = init_class.get_pull_request_files(
        TEST_ORG_NAME, TEST_REPO_NAME, TEST_PR_NUMBER, TEST_COMMIT_SHA
    )
    assert pull_files == [{"filename": "file1.py"}]


def test_get_pull_request_exclusion_files_without_download(
    init_class, project_level_exclusion_dict, mocker
):
    mock_response = [{"filename": "file1.py"}, {"filename": "file2.py"}]
    mock_session_response = MockSession(mock_response)

    mocker.patch("requests.Session.get", return_value=mock_session_response)
    mocker.patch(
        "isggithub.github.GitHub.get_project_level_service_config",
        return_value=project_level_exclusion_dict,
    )

    pull_files = init_class.get_pull_request_files(
        TEST_ORG_NAME, TEST_REPO_NAME, TEST_PR_NUMBER, TEST_COMMIT_SHA
    )
    assert pull_files == [{"filename": "file2.py"}]


@pytest.mark.parametrize(
    "mock_response",
    [
        {
            "data": {
                "organization": {
                    "name": TEST_ORG_NAME,
                    "repository": {
                        "name": TEST_REPO_NAME,
                        "branchProtectionRules": {
                            "edges": [{"node": "test"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": "Y3Vy5Q=="},
                        },
                    },
                }
            }
        },
        {"data": {"organization": {"name": TEST_ORG_NAME, "repository": None}}},
    ],
)
def test_get_repo_branch_protection_details(init_class, mocker, mock_response):
    mock_session_response = MockSession(mock_response)

    mocker.patch("requests.Session.post", return_value=mock_session_response)

    repo_details = init_class.get_repo_branch_protection_details(
        TEST_ORG_NAME, TEST_REPO_NAME
    )
    assert repo_details == mock_response


def test_get_repo_collaborators_details(init_class, mocker):
    mock_response = {
        "data": {
            "organization": {
                "name": TEST_ORG_NAME,
                "repository": {
                    "name": TEST_REPO_NAME,
                    "collaborators": {
                        "edges": [{"node": "test"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": "Y3Vy5Q=="},
                    },
                },
            }
        }
    }
    mock_session_response = MockSession(mock_response)

    mocker.patch("requests.Session.post", return_value=mock_session_response)

    repo_details = init_class.get_repo_collaborators_details(
        TEST_ORG_NAME, TEST_REPO_NAME
    )
    assert repo_details == mock_response


def test_set_github_status(init_class, mocker):
    mock_session = MockSession()
    mock_session.status_code = 201

    mocker.patch("requests.Session.post", return_value=mock_session)

    response_status_code = init_class.set_github_status(
        org_name=TEST_ORG_NAME,
        repo_name=TEST_REPO_NAME,
        commit_sha=TEST_COMMIT_SHA,
        checker_name=TEST_CHECKER_NAME,
        description="testing",
        details_url=TEST_DEATAIL_URL,
        state="success",
    )

    assert response_status_code == 201


def test_get_pull_request_details(init_class, mocker):
    mock_response = {"test_pr_details": {"key": "value"}}
    mock_session = MockSession(mock_response)

    mocker.patch("requests.Session.get", return_value=mock_session)

    response = init_class.get_pull_request_details(
        org_name=TEST_ORG_NAME, repo_name=TEST_REPO_NAME, pr_number=TEST_PR_NUMBER
    )

    assert response == mock_response


@pytest.mark.parametrize(
    "method, status_code",
    [
        ("get", 200),
        ("patch", 200),
        ("post", 200),
        ("delete", 200),
        ("put", 200),
        ("get", 500),
    ],
)
def test_custom_api_execute(init_class, mocker, method, status_code):
    mock_session = MockSession()
    mock_session.status_code = status_code

    mocker.patch("drpbase.utils.Utils.wait_for")
    mocker.patch("requests.Session.request", return_value=mock_session)

    url = f"/orgs/{TEST_ORG_NAME}/repos"
    response = init_class.custom_api_execute(method, url)
    assert response.status_code == status_code


def test_custom_api_execute_invalid_action(init_class, mocker):
    mock_session = MockSession()
    mock_session.status_code = None

    mocker.patch("requests.Session.request", return_value=mock_session)

    url = f"/orgs/{TEST_ORG_NAME}/repos"
    with pytest.raises(ValueError):
        init_class.custom_api_execute("test", url)
