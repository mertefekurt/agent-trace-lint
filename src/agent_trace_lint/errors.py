"""User-facing exceptions."""


class TraceLintError(Exception):
    """Base exception for expected CLI failures."""


class InputError(TraceLintError):
    """Raised when trace input cannot be parsed."""
