"""Exceptions for supernote cloud."""


class SupernoteException(Exception):
    """Base exception for supernote cloud."""


class ApiException(SupernoteException):
    """API exception."""
