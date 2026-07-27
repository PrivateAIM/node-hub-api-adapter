"""Create fake credentials for testing methods."""
import httpx2
from httpx2 import Request


class BearerAuth(httpx2.Auth):
    def __init__(self, token: str):
        self.__token = token

    def auth_flow(self, request: Request):
        request.headers["Authorization"] = f"Bearer {self.__token}"
        yield request
