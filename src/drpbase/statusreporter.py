from typing import Dict
from isgkafka.producer import KProducer
from drpbase import constant
import logging


class StatusReporter:
    TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, config: Dict):
        """
        Initialize Report
        Args:
            confing (Dict): The configuration of StatusReporter
        """
        self.logger = logging.getLogger(constant.LOGGER_NAME)
        self.status_mapping = {
            "queued": "begin",
            "in_progress": "begin",
            "completed": "end",
        }
        if config and config.get("producer_name", None):
            producer_name = config.get("producer_name")
            producer = constant.PRODUCERS.get_by_name(producer_name)
            if producer is None:
                raise ValueError(
                    "Error when creating StatusReporter with supplied configuration. No producer named {} found.".format(
                        producer_name
                    )
                )
            self.logger.info(
                "Framework status_reporter producer_name = %s", producer_name
            )
            self.producer = producer
        else:
            raise ValueError(
                "Error when creating StatusReporter with supplied configuration. No producer found."
            )

    def get_reply_state(self, check_run_status: str) -> str:
        """
        Get reply state, map from check run status
            "queued": "begin",
            "in_progress": "begin",
            "completed": "end"
        Args:
            check_run_status (str): Check run status
        Returns:
            str: the reply state
        """
        return self.status_mapping.get(check_run_status, "end")

    def send_report(
        self,
        org_name: str,
        repo_name: str,
        event_source_type: str,
        request_id: str,
        request_timestamp: str,
        reply_source: str,
        check_run_payload: Dict,
    ) -> Dict:
        """
        Send report to Kafka
        Args:
            org_name (str): organization name
            repo_name (str): repository name
            event_source_type (str): event source type
            request_id (str): request id
            request_timestamp(str): request id
            reply_source (str): reply source
            check_run_payload (Dict): check run payload
        Returns:
            Dict: report in json format
        """

        payload = self.generate_report(
            org_name,
            repo_name,
            event_source_type,
            request_id,
            request_timestamp,
            reply_source,
            check_run_payload,
        )

        self.producer.send(payload)
        return payload

    def generate_report(
        self,
        org_name: str,
        repo_name: str,
        event_source_type: str,
        request_id: str,
        request_timestamp: str,
        reply_source: str,
        check_run_payload: Dict,
    ) -> Dict:
        """
        Generate report to Kafka
        Args:
            org_name (str): organization name
            repo_name (str): repository name
            event_source_type (str): event source type
            request_id (str): request id
            request_timestamp (str): request timestamp
            reply_source (str): reply source
            check_run_payload (Dict): check run payload
        Returns:
            Dict
        """
        payload = {
            "eventSourceType": event_source_type,
            "replySource": reply_source,
            "requestId": request_id,
            "requestTimestamp": request_timestamp,
            "replyState": self.get_reply_state(check_run_payload["status"]),
            "result": check_run_payload.get("conclusion", None),
            "payload": {
                "org_name": org_name,
                "repo_name": repo_name,
                "check_run": check_run_payload,
            },
        }

        return payload

    def generate_check_run_payload(
        self,
        check_run_name: str,
        head_sha: str,
        status: str,
        title: str,
        summary: str,
        **kwargs,
    ) -> Dict:
        """
        Generate check run
        the payload of check-run is defined in https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28#create-a-check-run
        Args:
            check_run_name (str): Check-run name
            head_sha (str): head commit sha
            status (str): Status, one of 'queued', 'in_progress', or 'completed'
            title (str): title of the check run
            summary (str): summary of the check run
            kwargs (dict): Dictionary arguments, may contains following
                text: text of the check run
                details_url (str): Details url
                external_id (str): External id
                conclusion (str): Conclusion, one of 'success', 'failure', 'neutral', 'cancelled', 'timed_out', or 'action_required'
                completed_at (str): Completed at
                actions (list): Actions. object with 'label' 'description' 'identifier' 'icon_url'
        Returns:
            Dict
        """
        check_run_payload = {
            "name": check_run_name,
            "head_sha": head_sha,
            "status": status,
            "output": {
                "title": title,
                "summary": summary,
            },
        }

        if "details_url" in kwargs:
            check_run_payload["details_url"] = kwargs["details_url"]
        if "external_id" in kwargs:
            check_run_payload["external_id"] = kwargs["external_id"]
        if "started_at" in kwargs:
            check_run_payload["started_at"] = kwargs["started_at"].strftime(
                self.TIMESTAMP_FORMAT
            )
        if "completed_at" in kwargs:
            check_run_payload["completed_at"] = kwargs["completed_at"].strftime(
                self.TIMESTAMP_FORMAT
            )
        if "conclusion" in kwargs:
            check_run_payload["conclusion"] = kwargs["conclusion"]
        if "actions" in kwargs:
            check_run_payload["actions"] = kwargs["actions"]
        if "text" in kwargs:
            check_run_payload["output"]["text"] = kwargs["text"]

        return check_run_payload

    def update_check_run_payload(
        self,
        payload: Dict,
        **kwargs,
    ) -> Dict:
        """
        Update check run payload
        the payload of check-run is defined in https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28#create-a-check-run
        Args:
            payload (Dict): Check-run pyaload
            kwargs (dict): Dictionary arguments, may contains following
                name (str): Check-run name
                head_sha (str): head commit sha
                details_url (str): Details url
                external_id (str): External id
                status (str): Status, one of 'queued', 'in_progress', or 'completed'
                started_at (datetime): Completed at
                conclusion (str): Conclusion, one of 'success', 'failure', 'neutral', 'cancelled', 'timed_out', or 'action_required'
                completed_at (datetime): Completed at
                output (Dict): output of the check run
                actions (list): Actions. object with 'label' 'description' 'identifier' 'icon_url'
        Returns:
            Dict
        """
        if "name" in kwargs:
            payload["name"] = kwargs["name"]
        if "head_sha" in kwargs:
            payload["head_sha"] = kwargs["head_sha"]
        if "details_url" in kwargs:
            payload["details_url"] = kwargs["details_url"]
        if "external_id" in kwargs:
            payload["external_id"] = kwargs["external_id"]
        if "status" in kwargs:
            payload["status"] = kwargs["status"]
        if "started_at" in kwargs:
            payload["started_at"] = kwargs["started_at"].strftime(self.TIMESTAMP_FORMAT)
        if "completed_at" in kwargs:
            payload["completed_at"] = kwargs["completed_at"].strftime(
                self.TIMESTAMP_FORMAT
            )
        if "conclusion" in kwargs:
            payload["conclusion"] = kwargs["conclusion"]
        if "output" in kwargs:
            payload["output"] = kwargs["output"]
        if "actions" in kwargs:
            payload["actions"] = kwargs["actions"]

        return payload
