"""Custom exceptions for the engine module."""


class InvalidActionError(Exception):
    """Raised when an invalid action is attempted."""

    pass


class BarrierLimitError(Exception):
    """Raised when a barrier limit is exceeded."""

    pass


class IllegalBarrierPlacementError(Exception):
    """Raised when a barrier is placed illegally."""

    pass
