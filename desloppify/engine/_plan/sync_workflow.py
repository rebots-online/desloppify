"""Workflow gate sync — inject workflow action items when preconditions are met."""

from __future__ import annotations

from desloppify.engine._plan import stale_policy as stale_policy_mod
from desloppify.engine._plan._sync_context import has_objective_backlog
from desloppify.engine._plan.constants import (
    SUBJECTIVE_PREFIX,
    TRIAGE_IDS,
    WORKFLOW_COMMUNICATE_SCORE_ID,
    WORKFLOW_CREATE_PLAN_ID,
    WORKFLOW_IMPORT_SCORES_ID,
    WORKFLOW_SCORE_CHECKPOINT_ID,
    QueueSyncResult,
)
from desloppify.engine._plan.schema import PlanModel, ensure_plan_defaults
from desloppify.engine._plan.subjective_policy import SubjectiveVisibility
from desloppify.engine._state.schema import StateModel


def _no_unscored(
    state: StateModel,
    policy: SubjectiveVisibility | None,
) -> bool:
    """Return True when no unscored (placeholder) subjective dimensions remain."""
    if policy is not None:
        return not policy.unscored_ids
    return not stale_policy_mod.current_unscored_ids(
        state, subjective_prefix=SUBJECTIVE_PREFIX,
    )


def _inject(plan: PlanModel, item_id: str) -> QueueSyncResult:
    """Append *item_id* and clear stale skip entries for that workflow item."""
    order = plan["queue_order"]
    order.append(item_id)
    skipped = plan.get("skipped", {})
    if isinstance(skipped, dict):
        skipped.pop(item_id, None)
    return QueueSyncResult(injected=[item_id])


_EMPTY = QueueSyncResult


def sync_score_checkpoint_needed(
    plan: PlanModel,
    state: StateModel,
    *,
    policy: SubjectiveVisibility | None = None,
) -> QueueSyncResult:
    """Inject ``workflow::score-checkpoint`` when all initial reviews complete.

    Injects when:
    - No unscored (placeholder) subjective dimensions remain
    - ``workflow::score-checkpoint`` is not already in the queue

    Appended to back of queue.  Never reorders existing items.
    """
    ensure_plan_defaults(plan)
    order: list[str] = plan["queue_order"]

    if WORKFLOW_SCORE_CHECKPOINT_ID in order:
        return _EMPTY()
    if not _no_unscored(state, policy):
        return _EMPTY()
    return _inject(plan, WORKFLOW_SCORE_CHECKPOINT_ID)


def sync_create_plan_needed(
    plan: PlanModel,
    state: StateModel,
    *,
    policy: SubjectiveVisibility | None = None,
) -> QueueSyncResult:
    """Inject ``workflow::create-plan`` when reviews complete + objective backlog exists.

    Only injects when:
    - No unscored (placeholder) subjective dimensions remain
    - At least one objective issue exists
    - ``workflow::create-plan`` is not already in the queue
    - No triage stages are pending

    Appended to back of queue.  Never reorders existing items.
    """
    ensure_plan_defaults(plan)
    order: list[str] = plan["queue_order"]

    if WORKFLOW_CREATE_PLAN_ID in order:
        return _EMPTY()
    if any(sid in order for sid in TRIAGE_IDS):
        return _EMPTY()
    if not _no_unscored(state, policy):
        return _EMPTY()

    if not has_objective_backlog(state, policy):
        return _EMPTY()

    return _inject(plan, WORKFLOW_CREATE_PLAN_ID)


def sync_import_scores_needed(
    plan: PlanModel,
    state: StateModel,
    *,
    assessment_mode: str | None = None,
) -> QueueSyncResult:
    """Inject ``workflow::import-scores`` after issues-only import.

    Only injects when:
    - Assessment mode was ``issues_only`` (scores were skipped)
    - ``workflow::import-scores`` is not already in the queue

    Appended to back of queue.  Never reorders existing items.
    """
    ensure_plan_defaults(plan)
    order: list[str] = plan["queue_order"]

    if WORKFLOW_IMPORT_SCORES_ID in order:
        return _EMPTY()
    if assessment_mode != "issues_only":
        return _EMPTY()
    return _inject(plan, WORKFLOW_IMPORT_SCORES_ID)


class ScoreSnapshot:
    """Minimal score snapshot for rebaseline — avoids importing state.py."""

    __slots__ = ("strict", "overall", "objective", "verified")

    def __init__(
        self,
        *,
        strict: float | None,
        overall: float | None,
        objective: float | None,
        verified: float | None,
    ) -> None:
        self.strict = strict
        self.overall = overall
        self.objective = objective
        self.verified = verified


def sync_communicate_score_needed(
    plan: PlanModel,
    state: StateModel,
    *,
    policy: SubjectiveVisibility | None = None,
    scores_just_imported: bool = False,
    current_scores: ScoreSnapshot | None = None,
) -> QueueSyncResult:
    """Inject ``workflow::communicate-score`` and rebaseline scores.

    Injects when:
    - All initial subjective reviews are complete (no unscored dims), OR
      scores were just imported (trusted/attested/override)
    - ``workflow::communicate-score`` is not already in the queue
    - Score has not already been communicated this cycle
      (``previous_plan_start_scores`` absent)

    When injected and *current_scores* is provided, ``plan_start_scores``
    is rebaselined to the current score so the score display unfreezes at
    the new value.  The previous baseline is preserved in
    ``previous_plan_start_scores`` so the communicate-score queue item can
    show the old → new delta — and so mid-cycle scans know not to
    re-inject.
    """
    ensure_plan_defaults(plan)
    order: list[str] = plan["queue_order"]

    if WORKFLOW_COMMUNICATE_SCORE_ID in order:
        return _EMPTY()
    # Already communicated this cycle — previous_plan_start_scores is set
    # at injection time and cleared at cycle boundaries.
    if "previous_plan_start_scores" in plan:
        return _EMPTY()
    if not scores_just_imported and not _no_unscored(state, policy):
        return _EMPTY()

    if current_scores is not None:
        _rebaseline_plan_start_scores(plan, current_scores)
    # Set sentinel even when rebaseline was a no-op (no plan_start_scores
    # to rebaseline) so mid-cycle scans don't re-inject.
    if not plan.get("previous_plan_start_scores"):
        plan["previous_plan_start_scores"] = {}
    return _inject(plan, WORKFLOW_COMMUNICATE_SCORE_ID)


def _rebaseline_plan_start_scores(
    plan: PlanModel,
    scores: ScoreSnapshot,
) -> None:
    """Snapshot the current score as the new baseline, preserving the old one."""
    old_start = plan.get("plan_start_scores")
    if not isinstance(old_start, dict) or not old_start:
        return
    if scores.strict is None:
        return

    plan["previous_plan_start_scores"] = dict(old_start)
    plan["plan_start_scores"] = {
        "strict": scores.strict,
        "overall": scores.overall,
        "objective": scores.objective,
        "verified": scores.verified,
    }


__all__ = [
    "ScoreSnapshot",
    "sync_communicate_score_needed",
    "sync_create_plan_needed",
    "sync_import_scores_needed",
    "sync_score_checkpoint_needed",
]
