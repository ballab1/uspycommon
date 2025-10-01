################################################################################
# Copyright (c) 2022 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import logging
import jwt
import time
from datetime import datetime
from typing import Optional, Dict
import requests
from . import checkrun
from drpbase import constant
from drpbase.utils import Utils
from drpbase.restutils import RequestClient

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


class GitHubApp:
    """Class for running APIs to GitHub repository."""

    GITHUB_APP_ACCESS_TOKEN_EXPIRATION = 580  # seconds
    GITHUB_APP_ACCESS_TOKEN_EXPIRATION_CHECK = 540  # seconds

    def __init__(
        self,
        base_url: str,
        app_identifier: str,
        app_private_key: str,
        github_app_conf: dict,
    ):
        """
        Constructor for GitHub API object. User options need to be provided as part of configuration file.
        The following keys MUST be provided:
        {
            base_url: Base URL string for running GitHub APIs
            app_identifier: The app identifier for the GitHub app
            app_private_key: The private key for the GitHub app
        }

        Args:
            github_conf (dict): Dictonary of user configured values from configuration file
            app_identifier (str): The app identifier for the GitHub app
            app_private_key (str): The private key for the GitHub app
        """
        self.logger = logging.getLogger(constant.LOGGER_NAME)

        # Extract required args from config
        self.current_token = None
        self._base_url = base_url
        self.app_identifier = app_identifier
        self.app_private_key = app_private_key
        self.app_token_dict = {}
        self.installation_id_dict = {}

        retry_total = None
        # Override values if user provided them
        conf_retry_total = github_app_conf.get("retry", {}).get("total")
        if conf_retry_total is not None and isinstance(conf_retry_total, int):
            retry_total = conf_retry_total + 1

        self.client = RequestClient(requests.Session(), retry_total=retry_total)

    def _generate_access_token(self, org_name: str) -> Optional[str]:
        """
        Gererate access token for GitHub App
        calls: `POST /app/installations/{installation_id}/access_tokens <https://docs.github.com/en/free-pro-team@latest/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app>`_

        Args:
            org_name (str): Org name
            repo_name (str): Repo name

        Returns:
            str - access token
        """

        jwt_generated = jwt.encode(
            {
                "iat": int(time.time()),
                "exp": int(time.time()) + self.GITHUB_APP_ACCESS_TOKEN_EXPIRATION,
                "iss": self.app_identifier,
            },
            self.app_private_key,
            algorithm="RS256",
        )
        if type(jwt_generated) is bytes:
            jwt_generated = jwt_generated.decode("utf-8")

        headers = {
            "Authorization": "Bearer {}".format(jwt_generated),
            "Accept": "application/vnd.github.machine-man-preview+json",
        }
        self.client.gh_session.headers.update(headers)
        installation_id = None
        if org_name in self.installation_id_dict:
            installation_id = self.installation_id_dict[org_name]
        else:
            r = self.client.request_retry(
                "get", self._base_url + "/orgs/{}/installation".format(org_name)
            )
            installation_id = None
            if r.ok:
                installation_id = r.json()["id"]
                self.installation_id_dict[org_name] = installation_id
            else:
                self.logger.error(
                    "Failed to get installation id, reason:{}. Please check app installation on {}.".format(
                        r.content, org_name
                    )
                )
                return None

        r = self.client.request_retry(
            "post",
            self._base_url
            + "/app/installations/{}/access_tokens".format(installation_id),
        )

        if r.ok:
            return r.json()["token"]
        else:
            self.logger.error(
                "Failed to create access token, reason:{}".format(r.content)
            )
            return None

    def get_access_token_for_check(self, org_name: str) -> Optional[str]:
        """
        Get access token for GitHub App

        Args:
            org_name (str): Org name

        returns:
            Optional[str] - access token, the vaule will be None if failed to create access token
        """
        if (
            org_name in self.app_token_dict
            and int(time.time()) - self.app_token_dict[org_name][1]
            < self.GITHUB_APP_ACCESS_TOKEN_EXPIRATION_CHECK
        ):
            return self.app_token_dict[org_name][0]
        self.token_create_time = int(time.time())

        token = None
        token_create_time = 0
        retry = 3
        timesleep = 1
        while retry and not token:
            token_create_time = int(time.time())
            token = self._generate_access_token(org_name)
            if not token:
                time.sleep(timesleep)
                timesleep = timesleep * 3
            retry -= 1
        if token:
            self.app_token_dict[org_name] = (token, token_create_time)
        else:
            raise Exception("Failed to create access token for Github App")

        return token

    @Utils.exception_handler
    def find_existing_check(
        self, org_name: str, repo_name: str, commit: str, name: str
    ) -> Optional[checkrun.CheckRun]:
        """
        Find the checks which matches provided check_name.
        calls: `Get /repos/{org_name}/{repo_name}/commits/{commit}/check-runs <https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28#list-check-runs-for-a-git-reference>`_

        Args:
            org_name (str): Org name
            repo_name (str): Repo name
            commit (str): Commit sha
            check_name (str): Check name

        Returns:
            Optional[checkrun.CheckRun] object, the vaule will be None if failed to find the check
        """
        full_repo_name = org_name + "/" + repo_name
        self._update_request_client_header(org_name)
        r = self.client.request_retry(
            "get",
            self._base_url
            + "/repos/{}/commits/{}/check-runs?check_name={}&app_id={}".format(
                full_repo_name, commit, name, self.app_identifier
            ),
        )
        if r.ok:
            check_runs_result = r.json()
            if check_runs_result["total_count"] > 0:
                return checkrun.CheckRun(check_runs_result["check_runs"][0], self)
        return None

    @Utils.exception_handler
    def create_check_run(
        self,
        org_name: str,
        repo_name: str,
        name: str,
        commit: str,
        details_url: Optional[str] = None,
        external_id: Optional[str] = None,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        conclusion: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        output: Optional[dict] = None,
        actions: Optional[str] = None,
    ) -> Optional[checkrun.CheckRun]:
        """
        :calls: `POST /repos/{owner}/{repo}/check-runs <https://docs.github.com/en/rest/reference/checks#create-a-check-run>`_

        Args:
            org_name (str): Org name
            repo_name (str): Repo name
            check_name (str): Check-run name
            commit (str): Commit sha
            details_url (str): Details url
            external_id (str): External id
            status (str): Status, one of 'queued', 'in_progress', or 'completed'
            conclusion (str): Conclusion, one of 'success', 'failure', 'neutral', 'cancelled', 'timed_out', or 'action_required'
            completed_at (str): Completed at
            output (dict): Output
            actions (list): Actions

        Returns:
            CheckRun object
        """
        post_parameters = self._generate_check_run_request(
            name,
            commit,
            details_url,
            external_id,
            status,
            started_at,
            conclusion,
            completed_at,
            output,
            actions,
        )
        url = self._base_url + "/repos/{}/{}/check-runs".format(org_name, repo_name)
        data = self.send_check_run_request("post", org_name, url, post_parameters)
        return checkrun.CheckRun(data, self) if data else None

    @Utils.exception_handler
    def send_check_run_request(
        self, http_method: str, org_name: str, url: str, post_parameters: str
    ) -> Optional[Dict]:
        """
        Send check run request
        Args:
            http_method (Callable): Http method
            org_name (str): Org name
            url (str): Url
            post_parameters (str): Post parameters
        Return:
            Dict - check run data
        """
        self._update_request_client_header(org_name)
        r = self.client.request_retry(http_method, url, json=post_parameters)
        if r.ok:
            return r.json()
        else:
            self.logger.error(
                "failed to create check, result:{} , data:{}".format(
                    r.content, post_parameters
                )
            )
            return None

    @Utils.exception_handler
    def _generate_check_run_request(
        self,
        name: str,
        head_sha: str,
        details_url: Optional[str] = None,
        external_id: Optional[str] = None,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        conclusion: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        output: Optional[str] = None,
        actions: Optional[str] = None,
    ) -> Dict:
        post_parameters = {
            "name": name,
            "head_sha": head_sha,
        }
        if details_url is not None:
            post_parameters["details_url"] = details_url
        if external_id is not None:
            post_parameters["external_id"] = external_id
        if status is not None:
            post_parameters["status"] = status
        if started_at is not None:
            post_parameters["started_at"] = started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if completed_at is not None:
            post_parameters["completed_at"] = completed_at.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        if conclusion is not None:
            post_parameters["conclusion"] = conclusion
        if output is not None:
            post_parameters["output"] = output
        if actions is not None:
            post_parameters["actions"] = actions

        return post_parameters

    def _update_request_client_header(self, org_name: str) -> None:
        access_token = self.get_access_token_for_check(org_name)
        if self.current_token != access_token:
            header = {
                "Authorization": "Bearer {}".format(access_token),
                "Accept": "application/vnd.github.antiope-preview+json",
            }
            self.client.gh_session.headers.update(header)
            self.current_token = access_token
