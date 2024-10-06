"""Library for accessing backups in Supenote Cloud."""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

import aiohttp
from aiohttp.client_exceptions import ClientError
from mashumaro.mixins.json import DataClassJSONMixin

from .api_model import (
    UserLoginRequest,
    UserLoginResponse,
    UserRandomCodeRequest,
    UserRandomCodeResponse,
    FileListResponse,
    GetFileDownloadUrlRequest,
    GetFileDownloadUrlResponse,
    FileListRequest,
    QueryUserResponse,
    QueryUserRequest,
)
from .exceptions import ApiException

_LOGGER = logging.getLogger(__name__)

API_URL = "https://cloud.supernote.com/api"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
}
ACCESS_TOKEN = "x-access-token"

_T = TypeVar("_T", bound=DataClassJSONMixin)


def _sha256_s(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _md5_s(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _encode_password(password: str, rc: str) -> str:
    return _sha256_s(_md5_s(password) + rc)


class AbstractAuth(ABC):
    """Authentication library."""

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""


class ConstantAuth(AbstractAuth):
    """Authentication library."""

    def __init__(self, access_token: str):
        """Initialize the auth."""
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self._access_token


class Client:
    """Library that makes authenticated HTTP requests."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        host: str | None = None,
        auth: AbstractAuth | None = None,
    ):
        """Initialize the auth."""
        self._websession = websession
        self._host = host or API_URL
        self._auth = auth

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Make a request."""
        if headers is None:
            headers = {
                **HEADERS,
            }
        if self._auth and ACCESS_TOKEN not in headers:
            access_token = await self._auth.async_get_access_token()
            headers[ACCESS_TOKEN] = access_token
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self._host}/{url}"
        _LOGGER.debug("request[%s]=%s %s", method, url, kwargs.get("params"))
        if method != "get" and "json" in kwargs:
            _LOGGER.debug("request[post json]=%s", kwargs["json"])
        return await self._websession.request(method, url, **kwargs, headers=headers)

    async def get(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a get request."""
        try:
            resp = await self.request("get", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return await self._raise_for_status(resp)

    async def get_json(
        self,
        url: str,
        data_cls: Type[_T],
        **kwargs: Any,
    ) -> _T:
        """Make a get request and return json response."""
        resp = await self.get(url, **kwargs)
        try:
            result = await resp.text()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        _LOGGER.debug("response=%s", result)
        try:
            return data_cls.from_json(result)
        except (LookupError, ValueError) as err:
            raise ApiException(f"Server return malformed response: {result}") from err

    async def post(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a post request."""
        try:
            resp = await self.request("post", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return await self._raise_for_status(resp)

    async def post_json(self, url: str, data_cls: Type[_T], **kwargs: Any) -> _T:
        """Make a post request and return a json response."""
        resp = await self.post(url, **kwargs)
        try:
            result = await resp.text()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        _LOGGER.debug("response=%s", result)
        try:
            return data_cls.from_json(result)
        except (LookupError, ValueError) as err:
            raise ApiException(f"Server return malformed response: {result}") from err

    @classmethod
    async def _raise_for_status(
        cls, resp: aiohttp.ClientResponse
    ) -> aiohttp.ClientResponse:
        """Raise exceptions on failure methods."""
        error_detail = await cls._error_detail(resp)
        try:
            resp.raise_for_status()
        except aiohttp.ClientResponseError as err:
            error_message = f"Error response from API ({err.status}): {error_detail}"
            raise ApiException(error_message) from err
        except aiohttp.ClientError as err:
            raise ApiException(f"Error from API: {err}") from err
        return resp

    @classmethod
    async def _error_detail(cls, resp: aiohttp.ClientResponse) -> str | None:
        """Returns an error message string from the APi response."""
        if resp.status < 400:
            return None
        try:
            result = await resp.text()
        except ClientError:
            return None
        return result


class LoginClient:
    """A client library for logging in."""

    def __init__(self, client: Client):
        """Initialize the client."""
        self._client = client

    async def login(self, email: str, password: str) -> str:
        """Log in and return an access token."""
        random_code_response = await self._get_random_code(email)
        encoded_password = _encode_password(password, random_code_response.random_code)
        access_token_response = await self._get_access_token(
            email, encoded_password, random_code_response.timestamp
        )
        return access_token_response.token

    async def _get_random_code(self, email: str) -> UserRandomCodeResponse:
        """Get a random code."""
        payload = UserRandomCodeRequest(country_code=1, account=email).to_dict()
        return await self._client.post_json(
            "official/user/query/random/code", UserRandomCodeResponse, json=payload
        )

    async def _get_access_token(
        self, email: str, encoded_password: str, random_code_timestamp: str
    ) -> UserLoginResponse:
        """Get an access token."""
        payload = UserLoginRequest(
            country_code=1,
            account=email,
            password=encoded_password,
            browser="Chrome107",
            equipment=1,
            login_method=1,
            timestamp=random_code_timestamp,
            language="en",
        ).to_dict()
        return await self._client.post_json(
            "official/user/account/login/new", UserLoginResponse, json=payload
        )


class SupernoteCloudClient:
    """A client library for Supernote Cloud."""

    def __init__(self, client: Client):
        """Initialize the client."""
        self._client = client

    async def query_user(self, account: str) -> QueryUserResponse:
        """Query the user."""
        payload = QueryUserRequest(country_code=1, account=account).to_dict()
        return await self._client.post_json(
            "user/query", QueryUserResponse, json=payload
        )

    async def file_list(self, directory_id: int = 0) -> FileListResponse:
        """Return a list of files."""
        payload = FileListRequest(
            directory_id=directory_id,
            page_no=1,
            page_size=100,
            order="time",
            sequence="desc",
        ).to_dict()
        return await self._client.post_json(
            "file/list/query", FileListResponse, json=payload
        )

    async def file_download(self, file_id: int) -> bytes:
        """Download a file."""
        payload = GetFileDownloadUrlRequest(file_id=file_id, file_type=0).to_dict()
        download_url_response = await self._client.post_json(
            "file/download/url", GetFileDownloadUrlResponse, json=payload
        )
        response = await self._client.get(download_url_response.url)
        return await response.read()
