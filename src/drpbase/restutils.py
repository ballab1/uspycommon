import requests
import time
import logging
from drpbase import constant
from drpbase.utils import Utils


class RequestClient:
    # Defaults for rest request retry strategy
    RETRY_DEFAULT_TOTAL = 3
    RETRY_DEFAULT_SLEEPTIME = 10

    # Timeout for rest requests
    CONNECTION_DEFAULT_TIMEOUT = 6
    READ_DEFAULT_TIMEOUT = 60

    def __init__(
        self,
        gh_session: requests.sessions.Session,
        retry_total: int = None,
        timeout: tuple = None,
        retry_sleep_interval: int = None,
        check_ratelimit: bool = True,
    ):
        self.gh_session = gh_session
        self.status_forcelist = [429, 500, 502, 503, 504]
        self.logger = logging.getLogger(constant.LOGGER_NAME)

        # initialize parameters
        self.retry_total = self.RETRY_DEFAULT_TOTAL + 1
        self.retry_sleep_interval = self.RETRY_DEFAULT_SLEEPTIME
        self.timeout = (self.CONNECTION_DEFAULT_TIMEOUT, self.READ_DEFAULT_TIMEOUT)

        if retry_total is not None:
            self.retry_total = retry_total
        if timeout is not None:
            self.timeout = timeout
        if retry_sleep_interval is not None:
            self.retry_sleep_interval = retry_sleep_interval
        if check_ratelimit is not None:
            self._check_ratelimit = check_ratelimit

    @Utils.exception_handler
    def request_retry(self, action="", url="", **kwargs) -> object:
        """
        Makes API calls with retries.
        Checks ratelimit upon getting 403 github status code.

        Args:
            action (str)    : REST API methods example: get, patch, put etc.,
            url (str)       : Github url on which the request action needed to be made
            **kwargs (dict) : Dictionary arguments required by respective API methods

        Exception:
            An exception is thrown for any returned status other than success.

        Returns:
            Response object : Returns response object with respect to API call.
        """
        response = None
        post_response = None
        for attempt in range(self.retry_total):
            if action == "get":
                response = self.gh_session.get(url, timeout=self.timeout, **kwargs)
            elif action == "post":
                response = self.gh_session.post(url, timeout=self.timeout, **kwargs)
                post_response = response.json()
            elif action == "put":
                response = self.gh_session.put(url, timeout=self.timeout, **kwargs)
            elif action == "delete":
                response = self.gh_session.delete(url, timeout=self.timeout, **kwargs)
            elif action == "patch":
                response = self.gh_session.patch(url, timeout=self.timeout, **kwargs)
            else:
                raise ValueError("Invalid action type")

            if response.status_code in self.status_forcelist:
                self.logger.warning(
                    f"Requested action returned {response.status_code} status, attempting retry!!!"
                )
                # we need to retry. Before retrying we will wait for some time
                if attempt > 0:
                    self.logger.info(f"retry attempt {attempt} to {action} : {url}")
                Utils.wait_for(self.retry_sleep_interval * (2 ** (attempt)))
            elif response.status_code == 408:
                # Re-establishing the session upon 408 response status
                self.logger.warning(
                    f"Requested action returned {response.status_code} status, creating fresh session."
                )
                self.gh_session = self.requests_retry_session(requests.Session())
            elif response.status_code == 403:
                self.check_request_window(response.headers)
            elif (
                post_response
                and "errors" in post_response
                and post_response["errors"][0].get("type") == "RATE_LIMITED"
            ):
                # Condition for GQL ratelimit response
                self.check_request_window(response.headers)
            else:
                break

        if not str(response.status_code).startswith("2"):
            if response.status_code in self.status_forcelist:
                self.logger.error("retry attempts exceeded!")
            self.logger.error(
                "Communication error. Error code %s. Raising exception",
                response.status_code,
            )

        return response

    @Utils.exception_handler
    def check_request_window(self, response_header):
        """
        Upon reaching ratelimit sleep till next reset time.
        Reset time is obtained from the github response header.
        """
        if (
            self._check_ratelimit
            and "X-RateLimit-Remaining" in response_header
            and "X-RateLimit-Reset" in response_header
        ):
            # Getting ratelimit details
            remaining = int(response_header["X-RateLimit-Remaining"])
            resetAtTime = int(float(response_header["X-RateLimit-Reset"]))

            # Getting remaining time in seconds
            resetAfter = resetAtTime - int(time.time()) + 10
            self.logger.warning(
                f"Checking ratelimit, remaining API calls are:{remaining}\
                    Sleeping for {resetAfter} seconds to comply with Github reset time."
            )

            Utils.wait_for(resetAfter)
