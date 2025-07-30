################################################################################
# Copyright (c) 2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import copy
import json
import logging
import os
import shutil
import time
from typing import Optional

import requests
import yaml
from drpbase import constant
from drpbase.utils import Utils
from drpbase.restutils import RequestClient

from .gqlTemplate import gqlRepoBranchProtectionDetails, gqlRepoCollaboratorsDetails

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


class GitHub:
    """Class for running APIs to GitHub repository"""

    def __init__(self, github_conf: dict):
        """
        Constructor for GitHub API object. User options need to be provided as part of configuration file.
        The following keys MUST be provided:
        {
            base_url: Base URL string for running GitHub APIs
            token: Filename to get token for authenticating when running GitHub APIs
        }

        The following keys are optional. They all have built-in default values:
        {
            retry: {
                total: Int of total API retries
                backoff_factor: Int for retry interval backoff factor to apply between attempts
            }
        }

        Args:
            github_conf (dict): Dictonary of user configured values from configuration file
        """
        self.logger = logging.getLogger(constant.LOGGER_NAME)

        # Extract required args from config
        self._gql_url = Utils.get_config_value(github_conf, "gql_url", is_required=True)
        self._check_ratelimit = Utils.get_config_value(
            github_conf, "check_ratelimit", default=True
        )

        self._base_url = Utils.get_config_value(
            github_conf, "base_url", is_required=True
        )
        self._raw_github_url = Utils.get_config_value(
            github_conf, "raw_github_url", is_required=True
        )

        token_name = Utils.get_config_value(github_conf, "token", is_required=True)
        self._token = Utils.get_secret(token_name)

        self.project_level_config_folder = github_conf.get(
            "project_level_config_folder"
        )
        self.project_level_service_config_file = github_conf.get(
            "project_level_service_config_file"
        )
        self.global_exclusion_dict = github_conf.get("global_exclusion_list", {})

        retry_total = None
        # Override values if user provided them
        conf_retry_total = github_conf.get("retry", {}).get("total")
        if conf_retry_total is not None and isinstance(conf_retry_total, int):
            retry_total = conf_retry_total + 1

        # Setting up request timeout values
        timeout = None
        connection_timeout = Utils.get_config_value(
            github_conf, "connection_timeout_interval"
        )
        read_timeout = Utils.get_config_value(github_conf, "read_timeout_interval")
        if connection_timeout is not None and read_timeout is not None:
            timeout = (connection_timeout, read_timeout)

        retry_sleep_interval = None
        conf_retry_sleep_interval = github_conf.get("retry", {}).get(
            "retry_sleep_interval"
        )
        if conf_retry_sleep_interval is not None and isinstance(
            conf_retry_sleep_interval, int
        ):
            retry_sleep_interval = conf_retry_sleep_interval

        # Create a session attribute
        self.gh_session = self.requests_retry_session(requests.Session())
        self.client = RequestClient(
            self.gh_session, retry_total, timeout, retry_sleep_interval
        )

    @Utils.exception_handler
    def requests_retry_session(self, session: requests.Session) -> requests.Session:
        """
        Get the session object with headers and retry config settings for the API calls

        Args:
            session (object): Instance of requests.Session()

        Returns:
            requests.session(): Session object with headers and retry configurations
        """
        # Setting the header based on token source and requirement
        session.headers = {
            "Authorization": "token {}".format(self._token),
            "Accept": """application/vnd.github.sailor-v-preview+json application/\
                    vnd.github.eye-scream-preview+json application/vnd.github.luke-cage-preview+json\
                    application/vnd.github.loki-preview+json application/vnd.github.everest-preview+json""",
        }

        return session

    @Utils.exception_handler
    def _get_changed_files(
        self, org_name: str, repo_name: str, pr_number: int
    ) -> list[dict]:
        """
        Get the files that are changed in a given pull request

        Args:
            org_name (str)  : Org name for GitHub repo path
            repo_name (str) : Repo name for GitHub repo path
            pr_number (int) : pull request number

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            list[dict] : List of changed PR files, returns empty list if no files are present
        """
        self.logger.info("Getting changed pull request files")
        pull_url = "{}/repos/{}/{}/pulls/{}/files".format(
            self._base_url, org_name, repo_name, pr_number
        )
        pull_files = []

        params = {"per_page": 100}
        another_page = True

        # Get all the files changed in PR, 100 per page
        while another_page:

            response = self.client.request_retry("get", url=pull_url, params=params)
            response.raise_for_status()
            pull_files.extend(response.json())

            if "next" in response.links:
                pull_url = response.links["next"]["url"]
            else:
                another_page = False

        return pull_files

    @Utils.exception_handler
    def get_project_level_service_config(self, raw_url: str) -> dict:
        """
        Get project level checker configuration from project_level_config_folder/project_level_service_config_file

        Args:
            raw_url (str) : raw github url pointing to an repository in an organization

        Returns:
            dict : Project level exclusion and inclusion dictionaries,
                   If no project level config is found then returns empty dictionary.
        """
        self.logger.info("Getting project level service config")
        project_service_config = {}

        raw_file_url = "{}/{}/{}".format(
            raw_url,
            self.project_level_config_folder,
            self.project_level_service_config_file,
        )
        response = self.client.request_retry("get", url=raw_file_url)

        if response.ok:
            project_service_config = yaml.safe_load(response.text)
            self.logger.debug(
                "Fetching project level service config file: {}".format(
                    project_service_config
                )
            )
        else:
            self.logger.info(
                "Can not get project level service config file from {}".format(
                    raw_file_url
                )
            )

        return project_service_config

    @Utils.exception_handler
    def _filter_files(self, pr_files: list[dict], raw_url: str) -> list[dict]:
        """
        Filter files from PR files that match patterns and folders included in the project level
        config dict if present,

        Args:
            pr_files (list[dict]): List of changed files in PR
            raw_url (str)        : raw github url pointing to an repository in an organization

        Returns:
            list[dict] : List of dictionaries of filtered files after applying inclusions and exclusions,
                         Returns empty list if none present.
        """
        self.logger.info("Getting filtered pull request files")

        # Attempt to get project specific files config  in GitHub
        project_level_config_dict = self.get_project_level_service_config(raw_url)

        pull_files_list = []
        if project_level_config_dict.get("project_inclusion_list"):
            pull_files_list = self.filter_inclusion_files(
                project_level_config_dict.get("project_inclusion_list"), pr_files
            )
        else:
            pull_files_list = self.filter_exclusion_files(
                project_level_config_dict.get("project_exclusion_list"), pr_files
            )

        return pull_files_list

    @Utils.exception_handler
    def filter_exclusion_files(
        self, project_level_exclusion_dict: dict, pr_files: list[dict]
    ) -> list[dict]:
        """
        Filter files from PR files that match patterns and folders included in the project level config
        dict if present along with the global exclusion list, otherwise considers only global exclusion
        dict and Returns the list of filtered files with exclusions removed.

        Args:
            project_level_exclusion_dict (dict): exclusion list dictionary
            pr_files (list[dict])              : List of changed files in PR

        Returns:
            list[dict] : List of dictionaries of filtered files after applying exclusion configs,
                         Empty list if none present.
        """
        self.logger.info("Getting files after applying exclusion config")
        exclusion_dict = None
        if project_level_exclusion_dict is None:
            self.logger.info(
                "Project level config list is not defined. Using global exclusion dict"
            )
            exclusion_dict = self.global_exclusion_dict
        else:
            self.logger.info("Combining project level and global exclusion dict")
            exclusion_dict = Utils.get_combined_dict_of_list(
                project_level_exclusion_dict, self.global_exclusion_dict
            )

        # Extract items from exclusion dict
        exclusion_file_paths = exclusion_dict.get("exclusion_file_paths")
        exclusion_files_pattern = exclusion_dict.get("exclusion_files_pattern")
        exclusion_folders = exclusion_dict.get("exclusion_folders")

        # Loop through all files and test for matching with exclusion paths, patterns, and folders
        self.logger.info(
            "Filtering out files that match exclusion patterns and folders"
        )
        new_pull_files = []
        for file in pr_files:
            if (
                not Utils.match_with_exclusion_patterns(
                    file["filename"], exclusion_file_paths
                )
                and not Utils.match_with_exclusion_patterns(
                    file["filename"].split("/")[-1], exclusion_files_pattern
                )
                and not Utils.match_with_exclusion_folders(
                    file["filename"], exclusion_folders
                )
            ):
                new_pull_files.append(file)
                self.logger.info("Keep file: %s", file["filename"])
            else:
                self.logger.info("Exclude file: %s", file["filename"])

        return new_pull_files

    @Utils.exception_handler
    def filter_inclusion_files(
        self, project_level_inclusion_dict: dict, pr_files: list[dict]
    ) -> list[dict]:
        """
        Filter files from PR files that do not match patterns and folders included in the project level
        config dictionary if present.

        Args:
            project_level_inclusion_dict (dict)      : inclusion list dictionary
            pr_files (list[dict])                    : List of changed files in PR

        Returns:
            list[dict] : List of dictionaries of filtered files after applying inclusions,
                         Empty list if none present.
        """

        # Extract items from inclusion dict
        inclusion_file_paths = project_level_inclusion_dict.get("inclusion_file_paths")
        inclusion_files_pattern = project_level_inclusion_dict.get(
            "inclusion_files_pattern"
        )
        inclusion_folders = project_level_inclusion_dict.get("inclusion_folders")

        # Loop through all files and test for matching with inclusion paths, patterns, and folders
        self.logger.info(
            "Filtering out files that do not match inclusion patterns and folders"
        )
        new_pull_files = []
        for file in pr_files:
            if (
                not Utils.match_with_exclusion_patterns(
                    file["filename"], inclusion_file_paths
                )
                and not Utils.match_with_exclusion_patterns(
                    file["filename"].split("/")[-1], inclusion_files_pattern
                )
                and not Utils.match_with_exclusion_folders(
                    file["filename"], inclusion_folders
                )
            ):
                self.logger.info("Exclude file: %s", file["filename"])
            else:
                new_pull_files.append(file)
                self.logger.info("Keep file: %s", file["filename"])

        return new_pull_files

    @Utils.exception_handler
    def get_pull_request_files(
        self,
        org_name: str,
        repo_name: str,
        pr_number: int,
        commit_sha: str,
        filter_files: bool = True,
        local_workspace_dir: Optional[str] = None,
    ) -> list[dict]:
        """
        Get the changed PR files after applying inclusion and exclusion configuration.
        if local_workspace_dir is specified the PR files will be downloaded in the given
        directory path, otherwise only the list of changed PR files is returned without downloading.

        Args:
            org_name (str)            : Org name for GitHub repo path
            repo_name (str)           : Repo name for GitHub repo path
            pr_number (int)           : Pull request number
            commit_sha (str)          : Commit SHA for whose files are to be retreived
            filter_files (bool)       : If True, then exclusion and inclusion configs are applied on
                                        pull files. Default True.
            local_workspace_dir (str) : Name of the local workspace directory where the PR files will
                                        be downloaded.
        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            list[dict]: List of dictionaries of changed pull request files,
                        Empty list if none present.
        """
        raw_url = "{}/{}/{}/{}".format(
            self._raw_github_url, org_name, repo_name, commit_sha
        )

        # Get the changed files in PR
        pull_files = self._get_changed_files(org_name, repo_name, pr_number)

        filtered_files = pull_files
        if filter_files:
            # Apply exclusion and inclusion filters
            filtered_files = self._filter_files(pull_files, raw_url)

        # Check if workspace directory is provided, and then download the files if provided
        if local_workspace_dir:
            org_repo = f"{org_name}/{repo_name}"
            if os.path.exists(local_workspace_dir):
                shutil.rmtree(local_workspace_dir)

            full_repo = f"{self._base_url}/{org_repo}"
            self.logger.info(
                "Downloading changed files from PR #%i of repo %s to directory %s",
                pr_number,
                full_repo,
                local_workspace_dir,
            )

            # May hit issues with files larger than 1MB. See https://github.com/PyGithub/PyGithub/issues/661
            for pr_file in filtered_files:
                raw_file_url = "{}/{}".format(raw_url, pr_file["filename"])

                # Getting file content
                fileout = self.client.request_retry("get", url=raw_file_url)

                try:
                    fileout.raise_for_status()

                    file_path = os.path.join(local_workspace_dir, pr_file["filename"])
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    self.logger.info("The file path is: %s", file_path)

                    with open(file_path, "w") as file:
                        file.write(fileout.text)
                except UnicodeEncodeError:
                    self.logger.warning(
                        f"The file {pr_file['filename']} needs encoding."
                    )
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(fileout.text)
                except Exception as e:
                    self.logger.info(
                        f"Skipping download of {pr_file['filename']} due to error {e}"
                    )

        return filtered_files

    @Utils.exception_handler
    def get_pull_request_details(
        self, org_name: str, repo_name: str, pr_number: int
    ) -> dict:
        """
        Get the pull request details

        Args:
            org_name (str)  : Org name for GitHub repo path
            repo_name (str) : Repo name for GitHub repo path
            pr_number (int) : Pull request number

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            json (dictionary): pull request details
        """
        pull_url = "{}/repos/{}/{}/pulls/{}".format(
            self._base_url, org_name, repo_name, pr_number
        )
        self.logger.info("Pull Url: %s", pull_url)

        response = self.client.request_retry("get", url=pull_url)
        response.raise_for_status()

        output = response.json()
        self.logger.info("Pull Content: %s", str(response.json()))

        return output

    @Utils.exception_handler
    def set_github_status(
        self,
        org_name: str,
        repo_name: str,
        commit_sha: str,
        checker_name: str,
        description: str,
        details_url: str,
        state: str,
    ) -> int:
        """
        Set the github status

        Args:
            org_name (str)    : Org name for GitHub repo path
            repo_name (str)   : Repo name for GitHub repo path
            commit_sha (str)  : Commit SHA
            state (str)       : State of status to set.
            description (str) : Description of status
            checker_name (str): Context of status, usually the name of the service setting the status
            detail_url (str)  : URL containing additional information about context if provided.

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            int (status code): Response status code
        """
        status_url = "{}/repos/{}/{}/statuses/{}".format(
            self._base_url, org_name, repo_name, commit_sha
        )

        # Create JSON payload for setting status
        params = {
            "state": state,
            "target_url": details_url,
            "description": description,
            "context": checker_name,
        }
        data = json.dumps(params, sort_keys=True)

        response = self.client.request_retry("post", url=status_url, data=data)
        self.logger.info(f"Set Github Status Response: {response.status_code}")
        response.raise_for_status()

        return response.status_code

    @Utils.exception_handler
    def execute_gql(self, query) -> dict:
        """
        Execute github GQL query

        Args:
            query (str)  :  Github GQL query/mutation

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            json (dict) : response json of the given query
        """
        if isinstance(self._gql_url, str) is False:
            raise ValueError("GitHub 'gql_url' should be a string")

        response = self.client.request_retry(
            "post", self._gql_url, json={"query": query}
        )
        response.raise_for_status()

        return response.json()

    @Utils.exception_handler
    def get_repo_branch_protection_details(self, org_name: str, repo_name: str) -> dict:
        """
        Get repository branch protection details

        Args:
            org_name (str)    : Org name for GitHub repo path
            repo_name (str)   : Repo name for GitHub repo path

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            json (dict) : Branch protection rule details of given repo
        """
        cursor = ""
        content = dict()
        first_page = True
        next_page = True

        # Loop until there exists next page
        while next_page:
            query = gqlRepoBranchProtectionDetails.substitute(  # noqa 405
                org_name=f'"{org_name}"', repo_name=f'"{repo_name}"', cursor=cursor
            )
            res = self.execute_gql(query)

            if "data" in res and res["data"]["organization"]["repository"]:
                # Check if there is any branch protection rule applied for the repo
                if not len(
                    res["data"]["organization"]["repository"]["branchProtectionRules"][
                        "edges"
                    ]
                ):
                    content = res
                    break

                next_page = res["data"]["organization"]["repository"][
                    "branchProtectionRules"
                ]["pageInfo"]["hasNextPage"]

                # Set the cursor to point to next page, if exists
                cursor = (
                    'after: "'
                    + res["data"]["organization"]["repository"][
                        "branchProtectionRules"
                    ]["pageInfo"]["endCursor"]
                    + '"'
                )

                if first_page:
                    content = copy.deepcopy(res)
                    first_page = False
                    continue

                # Append the branch protection rules with previous page contents
                content["data"]["organization"]["repository"]["branchProtectionRules"][
                    "edges"
                ].extend(
                    res["data"]["organization"]["repository"]["branchProtectionRules"][
                        "edges"
                    ]
                )
            else:
                content = res
                break

        if "data" in res and res["data"]["organization"]["repository"]:
            content["data"]["organization"]["repository"]["branchProtectionRules"][
                "pageInfo"
            ]["hasNextPage"] = False

        return content

    @Utils.exception_handler
    def get_repo_collaborators_details(self, org_name: str, repo_name: str) -> dict:
        """
        Get repository collaborators details

        Args:
            org_name (str)    : Org name for GitHub repo path
            repo_name (str)   : Repo name for GitHub repo path

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            json (dict): Collaborators details of given repo
        """
        cursor = ""
        content = dict()
        first_page = True
        next_page = True

        # Loop until there exists next page
        while next_page:
            query = gqlRepoCollaboratorsDetails.substitute(  # noqa 405
                org_name=f'"{org_name}"', repo_name=f'"{repo_name}"', cursor=cursor
            )
            res = self.execute_gql(query)

            if "data" in res and res["data"]["organization"]["repository"]:
                # Check if there is exists any collaborators details
                if not len(
                    res["data"]["organization"]["repository"]["collaborators"]["edges"]
                ):
                    content = res
                    break

                next_page = res["data"]["organization"]["repository"]["collaborators"][
                    "pageInfo"
                ]["hasNextPage"]

                # Set the cursor to point to next page, if exists
                cursor = (
                    'after: "'
                    + res["data"]["organization"]["repository"]["collaborators"][
                        "pageInfo"
                    ]["endCursor"]
                    + '"'
                )

                if first_page:
                    content = copy.deepcopy(res)
                    first_page = False
                    continue

                # Append the collaborators details with previous page contents
                content["data"]["organization"]["repository"]["collaborators"][
                    "edges"
                ].extend(
                    res["data"]["organization"]["repository"]["collaborators"]["edges"]
                )
            else:
                content = res
                break

        if "data" in res and res["data"]["organization"]["repository"]:
            content["data"]["organization"]["repository"]["collaborators"]["pageInfo"][
                "hasNextPage"
            ] = False

        return content

    @Utils.exception_handler
    def custom_api_execute(
        self, method: str, endpoint: str, json_data: dict = None
    ) -> object:
        """
        Execute custom github rest api

        Args:
            method (str)     : Type of REST method, it can be GET, POST, PUT ot PATCH
            endpoint (str)   : Endpoint of the API that needs to be requested
            json_data (dict) : Json data that needs to be sent

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            Response object : Response json of a custom call
        """
        if endpoint[0] != "/":
            endpoint = "/" + endpoint

        url = self._base_url + endpoint
        response = None

        self.logger.info(
            f"Custom Github API endpoint {url} is called with {method} method."
        )
        if json_data is not None:
            response = self.client.request_retry(method, url, json=json_data)
        else:
            response = self.client.request_retry(method, url)
        response.raise_for_status()

        return response
