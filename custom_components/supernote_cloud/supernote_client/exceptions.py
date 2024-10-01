"""Exceptions for supernote cloud."""


class SupernoteException(Exception):
    """Base exception for supernote cloud."""


class AuthException(SupernoteException):
    """Authentication exception."""


class ApiException(SupernoteException):
    """API exception."""
