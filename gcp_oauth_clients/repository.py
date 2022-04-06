import abc
import logging
import pathlib
import sqlite3

from gcp_oauth_clients.tokens import TokenResponse

logger = logging.getLogger(__name__)


class BaseTokenRepository(abc.ABC):
    @property
    @abc.abstractmethod
    def filename(self) -> str:
        ...

    @abc.abstractmethod
    def store_tokens(self, *tokens: TokenResponse):
        ...

    @abc.abstractmethod
    def get_tokens(self) -> list[TokenResponse]:
        ...

    @abc.abstractmethod
    def get_tokens_with_scopes(self, *scopes: str) -> list[TokenResponse]:
        ...


class LocalTokenRepository(BaseTokenRepository):
    def __init__(self):
        self.conn = sqlite3.connect(self.filename)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS Tokens(
                access_token TEXT PRIMARY KEY,
                refresh_token TEXT,
                token_type TEXT,
                id_token TEXT NULL,
                expires_in INT,
                scope TEXT
            );
            """
        )
        logger.debug(f"Initialized LocalTokenRepository at {self.filename}")

    @property
    def filename(self) -> str:
        db_directory = pathlib.Path.home() / ".config" / "gcp_oauth_clients"
        db_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return str(db_directory / "tokens.db")

    def store_tokens(self, *tokens: TokenResponse):
        formatted_tokens = [
            (
                t.access_token,
                t.refresh_token,
                t.token_type,
                t.id_token,
                t.expires_in,
                "|".join(sorted(t.scope)),
            )
            for t in tokens
        ]

        self.conn.executemany(
            """
                INSERT INTO Tokens(
                    access_token, 
                    refresh_token, 
                    token_type, 
                    id_token, 
                    expires_in, 
                    scope
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
            formatted_tokens,
        )
        self.conn.commit()
        logger.debug(f"Stored {len(tokens)} tokens in LocalTokenRespository")

    def get_tokens(self) -> list[TokenResponse]:
        cur = self.conn.execute("SELECT * FROM Tokens")
        results = cur.fetchall()
        logger.debug(f"Retrieved {len(results)} tokens from LocalTokenRespository")
        return [
            TokenResponse(
                access_token=r["access_token"],
                refresh_token=r["refresh_token"],
                token_type=r["token_type"],
                id_token=r["id_token"],
                expires_in=r["expires_in"],
                scope=r["scope"].split("|"),
            )
            for r in results
        ]

    def get_tokens_for_scopes(self, *scopes: str) -> list[TokenResponse]:
        sorted_scopes = sorted(scopes)
        cur = self.conn.execute(
            "SELECT * FROM Tokens WHERE scope = ?", (sorted_scopes,)
        )
        results = cur.fetchall()
        logger.debug(f"Retrieved {len(results)} tokens from LocalTokenRespository")
        return [
            TokenResponse(
                access_token=r["access_token"],
                refresh_token=r["refresh_token"],
                token_type=r["token_type"],
                id_token=r["id_token"],
                expires_in=r["expires_in"],
                scope=r["scope"].split("|"),
            )
            for r in results
        ]
