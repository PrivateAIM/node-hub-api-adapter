"""Create fake credentials for testing methods."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from httpx import Request
from jose import jwk, jwt
from jose.constants import ALGORITHMS


@lru_cache()
def get_oid_test_jwk() -> dict:
    """Read and load a valid JWKS."""
    with open(
            Path(__file__).joinpath("..", "assets", "keypair.pem")
    ) as kf:
        jwks = jwk.RSAKey(algorithm=ALGORITHMS.RS256, key=kf.read().strip()).to_dict()

    return jwks


def issue_access_token(
        claims: dict[str, Any] | None = None,
        issued_at: datetime | None = None,
        expires_in: timedelta | None = None,
) -> str:
    if claims is None:
        claims = {}

    if issued_at is None:
        issued_at = datetime.now(tz=timezone.utc)

    if expires_in is None:
        expires_in = timedelta(hours=1)

    jwks = get_oid_test_jwk()

    token = jwt.encode(
        key=jwks,
        algorithm=ALGORITHMS.RS256,
        claims={
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + expires_in).timestamp()),
            **claims,
        },
    )

    return token


def issue_client_access_token(
        client_id: str = "test-client",
        issued_at: datetime | None = None,
        expires_in: timedelta | None = None,
):
    return issue_access_token(
        {
            "client_id": client_id,
        },
        issued_at,
        expires_in,
    )


class BearerAuth(httpx.Auth):
    def __init__(self, token: str):
        self.__token = token

    def auth_flow(self, request: Request):
        request.headers["Authorization"] = f"Bearer {self.__token}"
        yield request


fakeauth = BearerAuth(issue_client_access_token())
