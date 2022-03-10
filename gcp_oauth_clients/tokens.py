import typing as t

from pydantic import BaseModel, validator


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    scope: list[str]
    token_type: str = "Bearer"
    id_token: t.Optional[str] = None

    @validator("scope", pre=True)
    def parse_scopes(cls, v):
        return v.split(" ")
