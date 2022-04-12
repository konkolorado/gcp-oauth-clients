import json
import logging
import time
import typing as t
from contextlib import contextmanager
from pathlib import Path

import requests
from jose import jwt

from gcp_oauth_clients.exceptions import GcpOauthClientException
from gcp_oauth_clients.native import GcpNativeClient
from gcp_oauth_clients.server import LocalServer
from gcp_oauth_clients.tokens import TokenResponse

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
    def from_service_account_json(cls, key_file: str) -> "IapServiceAccountClient":
        if not Path(key_file).exists():
            raise GcpOauthClientException("The provided key file does not exist")

        with open(key_file) as infile:
            try:
                key_dict = json.load(infile)
            except json.JSONDecodeError as e:
                raise GcpOauthClientException(
                    "The provided key file is not in JSON format"
                ) from e
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
        return {"alg": "RS256", "typ": "JWT", "kid": self.private_key_id}

    def create_assertion(self, claims: dict) -> str:
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
                "assertion": self.create_assertion(payload),
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


class IapNativeClient(GcpNativeClient):
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.redirect_method = "server"
        self.redirect_uri: t.Optional[str] = None
        self.server: t.Optional[LocalServer] = None

    @property
    def authentication_url(self) -> str:
        if self.redirect_uri is None:
            raise GcpOauthClientException("New login has not been initialized")

        qargs = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "scope": "openid email",
        }
        req = requests.models.PreparedRequest()
        req.prepare_url(self.auth_url, qargs)
        logger.debug(f"Generated authentication_url={req.url}")
        return req.url  # type: ignore

    def exchange_authorization_code_for_tokens(
        self, _: t.Optional[str] = None
    ) -> TokenResponse:
        if self.redirect_uri is None or self.server is None:
            raise GcpOauthClientException("New login has not been initialized")
        result = self.server.get_result_blocking()
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": result.code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        resp = requests.post(self.tokens_url, data=data)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            logger.debug(
                "Exchanging authorization code for tokens failed", exc_info=True
            )
            raise GcpOauthClientException("Failed to exchange code for tokens")
        else:
            logger.debug("Exchanged authorization code for tokens")
            return TokenResponse(**resp.json())

    @contextmanager
    def new_login(self):
        self.server = self._start_local_server()
        self.redirect_uri = f"http://127.0.0.1:{self.server.port}"
        try:
            yield
        finally:
            self.server.shutdown()
            self.redirect_uri = None
            self.server = None

    def oidc_token_for_iap_client(self, refresh_token: str, iap_client_id: str) -> str:
        """
        Generates an OIDC token for use against a resource secured by the IAP
        client id provided
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "audience": iap_client_id,
        }
        resp = requests.post(self.tokens_url, data=data)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            logger.debug(
                "Exchanging authorization code for tokens failed", exc_info=True
            )
            raise GcpOauthClientException("Failed to exchange code for tokens")
        else:
            logger.debug("Exchanged authorization code for tokens")
            return resp.json()["id_token"]


