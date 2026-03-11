"""Shared degraded-plan warning helpers for resolve flows."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from desloppify.base.output.terminal import colorize

_DEGRADED_PLAN_WARNING_STATE = {"warned": False}


@dataclass(frozen=True)
class DegradedPlanWarning:
    """Structured degraded-mode warning payload for resolve flows."""

    error_kind: str | None
    message: str
    behavior: str


def warn_plan_load_degraded_once(
    *,
    error_kind: str | None,
    behavior: str,
) -> DegradedPlanWarning | None:
    """Print one consistent warning when resolve behavior degrades.

    Returns a structured warning payload on first emission, else ``None``.
    """
    if _DEGRADED_PLAN_WARNING_STATE["warned"]:
        return None
    _DEGRADED_PLAN_WARNING_STATE["warned"] = True

    detail = f" ({error_kind})" if error_kind else ""
    message = (
        "Warning: resolve is running in degraded mode because the living "
        f"plan could not be loaded{detail}."
    )
    warning = DegradedPlanWarning(
        error_kind=error_kind,
        message=message,
        behavior=behavior,
    )
    print(
        colorize(f"  {warning.message}", "yellow"),
        file=sys.stderr,
    )
    print(
        colorize(f"  {warning.behavior}", "dim"),
        file=sys.stderr,
    )
    return warning


def _reset_degraded_plan_warning_for_tests() -> None:
    """Test helper to reset warning dedupe state."""
    _DEGRADED_PLAN_WARNING_STATE["warned"] = False


__all__ = [
    "DegradedPlanWarning",
    "warn_plan_load_degraded_once",
]
