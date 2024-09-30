"""Model classes for the Supernote Cloud API."""

from dataclasses import dataclass, field

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class UserRandomCodeRequest(DataClassJSONMixin):
    """Request to get a random code."""

    country_code: int = field(metadata=field_options(alias="countryCode"))
    account: str


@dataclass
class UserRandomCodeResponse(DataClassJSONMixin):
    """Response from login."""

    random_code: str = field(metadata=field_options(alias="randomCode"))
    timestamp: str


@dataclass
class UserLoginRequest(DataClassJSONMixin):
    """Request to login."""

    country_code: int = field(metadata=field_options(alias="countryCode"))
    account: str
    password: str
    browser: str
    equipment: int
    login_method: int = field(metadata=field_options(alias="loginMethod"))
    timestamp: str
    language: str


@dataclass
class UserLoginResponse(DataClassJSONMixin):
    """Response from access token call."""

    token: str


@dataclass
class File(DataClassJSONMixin):
    """Representation of a file."""

    id: str
    directory_id: str = field(metadata=field_options(alias="directoryId"))
    file_name: str = field(metadata=field_options(alias="fileName"))
    size: int
    md5: str
    is_folder: str = field(metadata=field_options(alias="isFolder"))  # "Y" or "N"
    create_time: int = field(metadata=field_options(alias="createTime"))
    update_time: int = field(metadata=field_options(alias="updateTime"))


@dataclass
class FileListRequest(DataClassJSONMixin):
    """Request for file list."""

    directory_id: int = field(metadata=field_options(alias="directoryId"))
    page_no: int = field(metadata=field_options(alias="pageNo"))
    page_size: int = field(metadata=field_options(alias="pageSize"), default=20)
    order: str = "time"
    sequence: str = "desc"


@dataclass
class FileListResponse(DataClassJSONMixin):
    """Response from file list call."""

    success: bool
    error_code: str = field(metadata=field_options(alias="errorCode"))
    error_msg: str = field(metadata=field_options(alias="errorMsg"))
    total: int
    size: int
    pages: int
    file_list: list[File] = field(metadata=field_options(alias="userFileVOList"))


@dataclass
class GetFileDownloadUrlRequest(DataClassJSONMixin):
    """Request for file download."""

    file_id: int = field(metadata=field_options(alias="id"))
    file_type: int = field(metadata=field_options(alias="type"), default=0)


@dataclass
class GetFileDownloadUrlResponse(DataClassJSONMixin):
    """Response from file download call."""

    success: bool
    error_code: str = field(metadata=field_options(alias="errorCode"))
    error_msg: str = field(metadata=field_options(alias="errorMsg"))
    url: str
