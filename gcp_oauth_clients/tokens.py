import time
import typing as t

from pydantic import BaseModel, validator


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: t.Optional[str] = None
    expires_in: int
    scope: list[str]
    token_type: str = "Bearer"
    id_token: t.Optional[str] = None
    expires_at: int = None  # type: ignore

    @validator("scope", pre=True)
    def parse_scopes(cls, v):
        if isinstance(v, str):
            return v.split(" ")
        return v

    @validator("expires_at")
    def set_expires_at(cls, _, values):
        expires_in = values.get("expires_in")
        return int(time.time()) + expires_in
