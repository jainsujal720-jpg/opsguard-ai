"""Customer- and manager-friendly formatting helpers."""

from __future__ import annotations

from datetime import datetime


def friendly_time(value: str) -> str:
    """Convert an ISO timestamp into a natural 12-hour clock time."""
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%I:%M %p").lstrip("0")


def friendly_datetime(value: str) -> str:
    """Convert an ISO timestamp into a readable date and time."""
    parsed = datetime.fromisoformat(value)
    day = parsed.strftime("%d").lstrip("0")
    return f"{day} {parsed.strftime('%B %Y, %I:%M %p').replace(' 0', ' ')}"


def inr(amount: float | int) -> str:
    """Format an amount for human-facing Indian-rupee messages."""
    numeric = float(amount)
    rendered = f"{numeric:,.2f}" if not numeric.is_integer() else f"{numeric:,.0f}"
    return f"₹{rendered}"

