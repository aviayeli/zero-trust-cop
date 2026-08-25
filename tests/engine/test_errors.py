"""Tests for engine.errors module."""

import pytest

from engine.errors import (
    BarrierLimitError,
    IllegalBarrierPlacementError,
    InvalidActionError,
)


def test_invalid_action_error_exists():
    """Test that InvalidActionError exists and is a subclass of Exception."""
    assert issubclass(InvalidActionError, Exception)


def test_barrier_limit_error_exists():
    """Test that BarrierLimitError exists and is a subclass of Exception."""
    assert issubclass(BarrierLimitError, Exception)


def test_illegal_barrier_placement_error_exists():
    """Test that IllegalBarrierPlacementError exists and is a subclass of Exception."""
    assert issubclass(IllegalBarrierPlacementError, Exception)


def test_invalid_action_error_with_message():
    """Test that InvalidActionError can be raised with a message and caught."""
    message = "Invalid action performed"
    with pytest.raises(InvalidActionError) as exc_info:
        raise InvalidActionError(message)
    assert str(exc_info.value) == message


def test_barrier_limit_error_with_message():
    """Test that BarrierLimitError can be raised with a message and caught."""
    message = "Barrier limit exceeded"
    with pytest.raises(BarrierLimitError) as exc_info:
        raise BarrierLimitError(message)
    assert str(exc_info.value) == message


def test_illegal_barrier_placement_error_with_message():
    """Test that IllegalBarrierPlacementError can be raised with a message and caught."""
    message = "Illegal barrier placement detected"
    with pytest.raises(IllegalBarrierPlacementError) as exc_info:
        raise IllegalBarrierPlacementError(message)
    assert str(exc_info.value) == message
