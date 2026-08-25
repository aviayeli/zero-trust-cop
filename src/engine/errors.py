"""Custom exceptions for the engine module."""


class InvalidActionError(Exception):
    """Raised when an invalid action is attempted."""



class BarrierLimitError(Exception):
    """Raised when a barrier limit is exceeded."""



class IllegalBarrierPlacementError(Exception):
    """Raised when a barrier is placed illegally."""

