import logging
import time
import typing as t
from contextlib import contextmanager

import requests
from jose import jwt

from gcp_oauth_clients.exceptions import GcpOauthClientException
from gcp_oauth_clients.tokens import TokenResponse

logger = logging.getLogger(__name__)


class GcpConfidentialClient:

    tokens_url = "https://oauth2.googleapis.com/token"
    exp_in_s = 60 * 60  # 1 hour is max TTL

    def __init__(self, client_id: str, client_secret: str):
        """
        A class-based implementation for OAuth2 Confidential Apps on GCP. This
        allows confidential apps (or clients) to perform OAuth2 logins for
        access tokens to GCP APIs.

        For pre-requisites on creating a GCP service account and secret, follow
        the instructions at the link below:


        https://developers.google.com/identity/protocols/oauth2/service-account#creatinganaccount
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes: t.Optional[tuple[str, ...]] = None

    @property
    def jwt_header(self) -> dict[str, str]:
        return {"alg": "RS256", "typ": "JWT"}

    @property
    def jwt_claim_set(self) -> dict[str, t.Union[str, int]]:
        if self.scopes is None:
            raise GcpOauthClientException("New login has not been initialized")

        return {
            "iss": self.client_id,
            "scope": " ".join(self.scopes),
            "aud": "https://oauth2.googleapis.com/token",
            "exp": int(time.time()) + self.exp_in_s,
            "iat": int(time.time()),
        }

    @property
    def jwt(self) -> str:
        return jwt.encode(
            self.jwt_claim_set,
            self.client_secret,
            algorithm="RS256",
            headers=self.jwt_header,
        )

    def get_tokens(self):
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": self.jwt,
        }
        resp = requests.post(self.tokens_url, data=data)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            logger.debug("Failed to get tokens", exc_info=True)
            raise GcpOauthClientException("Failed to exchange code for tokens")
        else:
            logger.debug(f"Received tokens for scope(s) {', '.join(self.scopes)}")
            full_token_response = {**resp.json(), "scope": " ".join(self.scopes)}
            return TokenResponse(**full_token_response)

    @contextmanager
    def new_login(self, *scopes: str):
        if len(scopes) == 0:
            raise GcpOauthClientException("At least one scope is required")
        self.scopes = scopes

        try:
            yield
        finally:
            self.scopes = None
