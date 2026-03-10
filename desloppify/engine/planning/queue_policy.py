"""Queue-policy helpers shared by planning render/select modules."""

from __future__ import annotations

from dataclasses import dataclass, replace

from desloppify.base.config import DEFAULT_TARGET_STRICT_SCORE
from desloppify.engine._state.schema import StateModel
from desloppify.engine._work_queue.core import (
    QueueBuildOptions,
    WorkQueueResult,
    build_work_queue,
)


def _subjective_threshold(state: StateModel, *, default: float = DEFAULT_TARGET_STRICT_SCORE) -> float:
    config = state.get("config", {})
    raw_target = default
    if isinstance(config, dict):
        raw_target = config.get("target_strict_score", default)
    try:
        value = float(raw_target)
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(100.0, value))


@dataclass(frozen=True, slots=True)
class OpenPlanQueuePolicy:
    count: int | None = None
    scan_path: str | None = None
    include_subjective: bool = True


def _queue_shaping_plan_present(plan: dict | None) -> bool:
    if not isinstance(plan, dict):
        return False
    return bool(plan.get("queue_order") or plan.get("overrides") or plan.get("clusters"))


def _queue_plan_from_options(options: QueueBuildOptions) -> dict | None:
    if options.context is not None:
        return options.context.plan
    return options.plan


def build_open_plan_queue(
    state: StateModel,
    policy: OpenPlanQueuePolicy | None = None,
) -> WorkQueueResult:
    """Build one open-status queue with consistent planning policy defaults."""
    policy = policy or OpenPlanQueuePolicy()
    # When policy.scan_path is explicitly set, override the auto-default.
    # Otherwise let QueueBuildOptions read from state automatically.
    scan_path_kwarg: dict = (
        {"scan_path": policy.scan_path} if policy.scan_path is not None else {}
    )
    return build_work_queue(
        state,
        options=QueueBuildOptions(
            count=policy.count,
            status="open",
            include_subjective=policy.include_subjective,
            subjective_threshold=_subjective_threshold(state),
            **scan_path_kwarg,
        ),
    )


def build_execution_queue(
    state: StateModel,
    *,
    options: QueueBuildOptions | None = None,
) -> WorkQueueResult:
    """Build the execution queue that follows the living plan when present."""
    options = options or QueueBuildOptions()
    if not _queue_shaping_plan_present(_queue_plan_from_options(options)):
        return build_work_queue(state, options=options)
    return build_work_queue(
        state,
        options=replace(options, planned_only=True),
    )


def build_backlog_queue(
    state: StateModel,
    *,
    options: QueueBuildOptions | None = None,
) -> WorkQueueResult:
    """Build the broader backlog, excluding work already tracked in the plan."""
    options = options or QueueBuildOptions()
    if not _queue_shaping_plan_present(_queue_plan_from_options(options)):
        return build_work_queue(state, options=options)
    return build_work_queue(
        state,
        options=replace(options, exclude_plan_tracked=True),
    )


__all__ = [
    "OpenPlanQueuePolicy",
    "build_backlog_queue",
    "build_execution_queue",
    "build_open_plan_queue",
]
