################################################################################
# Copyright (c) 2023 Dell Inc. or its subsidiaries.  All rights reserved.
################################################################################
import base64
import datetime
import logging

import jwt
import requests
from drpbase import constant

logger = logging.getLogger(constant.LOGGER_NAME)

# Constants related to jwt authentication
DRP_API_JWT_SECRET = "shared-secret"
DRP_API_JWT_ALGORITHM = "HS256"
SSO_SP_URL = "https://dl1v3auth1.cec.lab.emc.com:8443"


class JWTAuthentication:
    """Class for authenticating the backend API's using JWT token."""

    @staticmethod
    def issue_jwt(payload: dict) -> str:
        """
        Issues JWT token.

        A helper method to create tokens.
        Payload is altered to add expiry claim.
        10 minutes is added to expiry claim so that
        when the token expires, it can be used to
        re-authenticate with the real authentication service.
        That makes normal GUI operations faster and reduces load on the authentication server,
        at the cost that authentication changes might take ten minutes to take effect

        Sample payload with expiry claim
            {
            "username": "narayana_chunduri",
            "firstName": "Narayana",
            "lastName": "Chunduri",
            "email": "Narayana_Chunduri@Dell.com",
            "sso_token": "XXXXXXXXXXXXXXXXXXXXXXX",
            "exp": 1626901660
            }

            Returns
                String corresponding to the payload.
        """
        payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        return jwt.encode(
            payload,
            DRP_API_JWT_SECRET,
            algorithm=DRP_API_JWT_ALGORITHM,
        )

    @staticmethod
    def validate_jwt(json_web_token):
        """
        Validate JWT token.

        Returns
            Same token if input is a valid unexpired token, or
            None if input token is invalid or sso_token is expired, or
            New token if current jwt token has expired but sso_token hasn't expired
        """
        try:
            json_web_token = jwt.decode(
                json_web_token,
                DRP_API_JWT_SECRET,
                algorithms=[DRP_API_JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            decoded_token = jwt.decode(
                json_web_token,
                DRP_API_JWT_SECRET,
                options={"verify_exp": False},
                algorithms=[DRP_API_JWT_ALGORITHM],
            )
            sso_token = decoded_token.get("sso_token")
            """ rbac-test is a test user in drp UI where the users have the capability to
                perform testing of the web application, logging in as a different user. """

            if sso_token == "rbac-test":
                payload = {
                    "username": "rbac-test",
                    "firstName": "RBAC",
                    "lastName": "Test",
                    "email": "rbac-test@dell.com",
                    "sso_token": "rbac-test",
                }
            else:
                payload = JWTAuthentication.get_sso_user_details(sso_token)

            if payload:
                json_web_token = JWTAuthentication.issue_jwt(payload)
                logger.debug(
                    "The token has expired.Generated new token for",
                    extra={
                        "username": payload.get("username"),
                        "email": payload.get("email"),
                        "exp": payload.get("exp"),
                    },
                )
            else:
                json_web_token = None
                logger.debug("The token has expired and the payload is not available")
        except Exception as exp:
            json_web_token = None
            logger.debug(
                "General exception thrown while decoding the jwt token {}".format(exp)
            )
        return json_web_token

    @staticmethod
    def get_sso_user_details(sso_token):
        """
        Fetch logged in user details from third party SSO SP using sso_token.

        Sample response from SP
        {
            "result": {
                "username": "",
                "firstName": "",
                "lastName": "",
                "email": "",
                "authority": "BYOS_USER"
            }
        }

        Returns
            None if sso_token is invalid or
            dict. Sample dict is
                {
                    "username": "",
                    "firstName": "",
                    "lastName": "",
                    "email": "",
                    "sso_token": ""
                }
        """
        user_details_endpoint = SSO_SP_URL + "/api/ui/self"
        headers = {
            "Authorization": "Bearer " + base64.b64decode(sso_token).decode("ascii")
        }
        try:
            response = requests.get(user_details_endpoint, headers=headers)
        except Exception as e:
            logger.debug(
                "Cannot connect to SSO SP due to the following error {}".format(e)
            )
            return None
        user_details = (
            response.json().get("result") if "error" not in response.json() else None
        )
        if user_details:
            user_details.pop("authority", None)
            user_details["sso_token"] = sso_token
        return user_details
