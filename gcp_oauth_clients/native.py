import base64
import hashlib
import logging
import os
import re
import typing as t
from contextlib import contextmanager

import requests

from gcp_oauth_clients.exceptions import GcpOauthClientException
from gcp_oauth_clients.server import LocalServer
from gcp_oauth_clients.tokens import TokenResponse

logger = logging.getLogger(__name__)


class GcpNativeClient:
    auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    tokens_url: str = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_method: t.Literal["manual", "server"] = "manual",
    ):
        """
        A class-based implementation for OAuth2 Native Apps on GCP. This allows
        Native apps (or clients) to run OAuth2 logins on behalf of a user to
        access GCP APIs.

        For pre-requisites on creating a GCP client and secret, follow the
        instructions at the link below, taking care to set the application type
        to "Desktop app" and the client's visibility to public. Because it is
        public, the client secret must be included however it cannot (and will
        not) be used to facilitate authentication.

        https://developers.google.com/identity/protocols/oauth2/native-app#prerequisites
        """

        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.redirect_method = redirect_method
        self.code_challenge: t.Optional[str] = None
        self.code_verifier: t.Optional[str] = None
        self.state: t.Optional[str] = None
        self.redirect_uri: t.Optional[str] = None
        self.server: t.Optional[LocalServer] = None
        self.scopes: t.Optional[tuple[str, ...]] = None

    def _generate_code_verifier(self) -> str:
        verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        verifier = re.sub("[^a-zA-Z0-9]+", "", verifier)
        logger.debug(f"Generated code verifier {verifier=}")
        return verifier

    def _generate_code_challenge(self) -> str:
        if self.code_verifier is None:
            raise GcpOauthClientException("New login has not been initialized")

        challenge_sha = hashlib.sha256(self.code_verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(challenge_sha).decode("utf-8")
        challenge = challenge.replace("=", "")
        logger.debug(f"Generated code challenge {challenge=}")
        return challenge

    def _generate_state(self) -> str:
        state = hashlib.sha256(os.urandom(1024)).hexdigest()
        logger.debug(f"Generated authentication state {state=}")
        return state

    def _start_local_server(self) -> LocalServer:
        server = LocalServer()
        server.run()
        return server

    @property
    def authentication_url(self) -> str:
        if (
            self.code_challenge is None
            or self.redirect_uri is None
            or self.state is None
            or self.scopes is None
        ):
            raise GcpOauthClientException("New login has not been initialized")

        qargs = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "login_hint": "",
        }
        req = requests.models.PreparedRequest()
        req.prepare_url(self.auth_url, qargs)
        logger.debug(f"Generated authentication_url={req.url}")
        return req.url  # type: ignore

    def exchange_authorization_code_for_tokens(
        self, code: t.Optional[str] = None
    ) -> TokenResponse:
        if self.code_verifier is None or self.redirect_method is None:
            raise GcpOauthClientException("New login has not been initialized")

        if self.redirect_method == "server":
            if self.server is None:
                raise GcpOauthClientException("New login has not been initialized")
            result = self.server.get_result_blocking()
            if result.state != self.state:
                raise GcpOauthClientException("Invalid state returned during login")
            code = result.code
            self.server.shutdown()
        elif code is None:
            raise GcpOauthClientException("A code is required in manual mode")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "code_verifier": self.code_verifier,
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
    def new_login(self, *scopes: str):
        if len(scopes) == 0:
            raise GcpOauthClientException("At least one scope is required")

        self.scopes = scopes
        self.code_verifier = self._generate_code_verifier()
        self.code_challenge = self._generate_code_challenge()
        self.state = self._generate_state()

        if self.redirect_method == "server":
            self.server = self._start_local_server()
            self.redirect_uri = f"http://127.0.0.1:{self.server.port}"
        else:
            self.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        try:
            yield
        finally:
            self.scopes = None
            self.code_verifier = None
            self.code_challenge = None
            self.state = None
            self.redirect_uri = None
            self.server = None
