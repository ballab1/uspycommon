from datetime import datetime
from typing import Any, Optional, Dict
from dateutil import parser
from . import checkrunoutput


class CheckRun:
    """
    This class represents a check run.
    The reference can be found here
    https://docs.github.com/en/rest/reference/checks#check-runs
    """

    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"

    CONCLUSION_ACTION_REQUIRED = "action_required"
    CONCLUSION_CANCELLED = "cancelled"
    CONCLUSION_FAILURE = "failure"
    CONCLUSION_NEUTRAL = "neutral"
    CONCLUSION_SUCCESS = "success"
    CONCLUSION_SKIPPED = "skipped"
    CONCLUSION_STALE = "stale"
    CONCLUSION_TIMED_OUT = "timed_out"

    def __init__(self, data, github_app):
        self.github_app = github_app
        self.completed_at = None
        self.conclusion = None
        self.details_url = None
        self.external_id = None
        self.head_sha = None
        self.id = None
        self.name = None
        self.node_id = None
        self.output = None
        self.started_at = None
        self.status = None
        self.url = None
        self._useAttributes(data)

    def update(
        self,
        name: Optional[str] = None,
        head_sha: Optional[str] = None,
        details_url: Optional[str] = None,
        external_id: Optional[str] = None,
        status: Optional[str] = None,
        started_at: Optional[datetime] = None,
        conclusion: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        output: Optional[Dict] = None,
        actions: Optional[list[Dict]] = None,
    ) -> None:
        """
        :calls: `PATCH /repos/{owner}/{repo}/check-runs/{check_run_id}
        <https://docs.github.com/en/rest/reference/checks#update-a-check-run>`_
        """

        params: Dict[str, Any] = {}
        if name is not None:
            params["name"] = name
        if head_sha is not None:
            params["head_sha"] = head_sha
        if details_url is not None:
            params["details_url"] = details_url
        if external_id is not None:
            params["external_id"] = external_id
        if status is not None:
            params["status"] = status
        if started_at is not None:
            params["started_at"] = started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if completed_at is not None:
            params["completed_at"] = completed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if conclusion is not None:
            params["conclusion"] = conclusion
        if output is not None:
            params["output"] = output
        if actions is not None:
            params["actions"] = actions

        org_name = self.url.split("/repos/")[-1].split("/")[0]
        data = self.github_app.send_check_run_request(
            "patch", org_name, self.url, post_parameters=params
        )
        self._useAttributes(data)

    def _convertDatetime(self, datetimeString: str) -> Optional[datetime]:
        if datetimeString is None:
            return None
        return parser.parse(datetimeString)

    def _useAttributes(self, attributes: Dict[str, Any]) -> None:
        if "completed_at" in attributes:
            self.completed_at = self._convertDatetime(attributes["completed_at"])
        if "conclusion" in attributes:
            self.conclusion = attributes["conclusion"]
        if "details_url" in attributes:
            self.details_url = attributes["details_url"]
        if "external_id" in attributes:
            self.external_id = attributes["external_id"]
        if "head_sha" in attributes:
            self.head_sha = attributes["head_sha"]
        if "id" in attributes:
            self.id = attributes["id"]
        if "name" in attributes:
            self.name = attributes["name"]
        if "node_id" in attributes:
            self.node_id = attributes["node_id"]
        if "output" in attributes:
            self.output = checkrunoutput.CheckRunOutput(attributes["output"])
        if "started_at" in attributes:
            self.started_at = self._convertDatetime(attributes["started_at"])
        if "status" in attributes:
            self.status = attributes["status"]
        if "url" in attributes:
            self.url = attributes["url"]
