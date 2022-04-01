import json
import logging
import time
from pathlib import Path

import requests
from jose import jwt

from gcp_oauth_clients.exceptions import GcpOauthClientException

logger = logging.getLogger(__name__)


class IapServiceAccountClient:
    tokens_url = "https://www.googleapis.com/oauth2/v4/token"

    def __init__(
        self,
        *,
        client_id: str,
        client_email: str,
        private_key_id: str,
        private_key: str,
    ):
        self.client_id = client_id
        self.client_email = client_email
        self.private_key_id = private_key_id
        self.private_key = private_key

    @classmethod
    def from_key_file(cls, key_file: str) -> "IapServiceAccountClient":
        if not Path(key_file).exists():
            raise GcpOauthClientException("The provided key file does not exist")

        with open(key_file) as infile:
            try:
                key_dict = json.load(infile)
            except json.JSONDecodeError:
                raise GcpOauthClientException(
                    "The provided key file is not in JSON format"
                )
        try:
            return cls(
                client_id=key_dict["client_id"],
                client_email=key_dict["client_email"],
                private_key_id=key_dict["private_key_id"],
                private_key=key_dict["private_key"],
            )
        except KeyError as e:
            raise GcpOauthClientException(
                "The provided key file does not contain the expected key(s)"
            ) from e

    @property
    def headers(self) -> dict[str, str]:
        return {"alg": "RS256", "typ": "JWT", "kid": self.private_key}

    def create_assertions(self, claims: dict) -> str:
        return jwt.encode(
            claims, self.private_key, algorithm="RS256", headers=self.headers
        )

    def oidc_token_for_iap_client(self, iap_client_id: str) -> str:
        """
        Generates an OIDC token for use against a resource secured by the IAP
        client id provided
        """
        payload = {
            "iss": self.client_email,
            "aud": "https://oauth2.googleapis.com/token",
            "exp": int(time.time()) + 60,
            "iat": int(time.time()),
            "sub": self.client_email,
            "target_audience": iap_client_id,
        }

        resp = requests.post(
            self.tokens_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertions": self.create_assertions(payload),
            },
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            logger.debug("Failed to obtain OIDC token", exc_info=True)
            raise GcpOauthClientException("Failed to obtain OIDC token")
        else:
            logger.debug("Obtained OIDC token")
            return resp.json()["id_token"]
