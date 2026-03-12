"""Review-coverage helpers for triage planning."""

from __future__ import annotations

from desloppify.app.commands.plan.shared.cluster_membership import cluster_issue_ids
from desloppify.engine._plan.policy.stale import open_review_ids
from desloppify.engine._state.schema import StateModel
from desloppify.engine.plan_state import Cluster, PlanModel

from .plan_state_access import (
    ensure_cluster_map,
    ensure_queue_order,
    ensure_skipped_map,
    ensure_triage_meta,
    normalized_issue_id_list,
)

_ACTIVE_TRIAGE_ISSUE_IDS_KEY = "active_triage_issue_ids"
_UNDISPOSITIONED_TRIAGE_ISSUES_KEY = "undispositioned_issue_ids"
_UNDISPOSITIONED_TRIAGE_COUNT_KEY = "undispositioned_issue_count"


def open_review_ids_from_state(state: StateModel) -> set[str]:
    """Return open review IDs from the current state snapshot."""
    return open_review_ids(state)


def has_open_review_issues(state: StateModel | dict | None) -> bool:
    """Return True when any open review issues exist."""
    return bool(open_review_ids_from_state(state or {}))


def plan_review_ids(plan: PlanModel) -> list[str]:
    """Return review/concerns IDs currently represented in queue_order."""
    return [
        fid
        for fid in ensure_queue_order(plan)
        if not fid.startswith("triage::")
        and not fid.startswith("workflow::")
        and (fid.startswith("review::") or fid.startswith("concerns::"))
    ]


def coverage_open_ids(plan: PlanModel, state: StateModel) -> set[str]:
    """Return the frozen or live open review IDs covered by this triage run."""
    active_ids = normalized_issue_id_list(
        ensure_triage_meta(plan).get(_ACTIVE_TRIAGE_ISSUE_IDS_KEY)
    )
    if active_ids:
        return set(active_ids)
    has_completed_scan = bool(state.get("last_scan"))
    review_ids = open_review_ids_from_state(state)
    if not has_completed_scan and not review_ids:
        return set(plan_review_ids(plan))
    return review_ids


def active_triage_issue_ids(
    plan: PlanModel,
    state: StateModel | None = None,
) -> set[str]:
    """Return the frozen review issue set for the current triage run."""
    meta = ensure_triage_meta(plan)
    active_ids = normalized_issue_id_list(meta.get(_ACTIVE_TRIAGE_ISSUE_IDS_KEY))
    if active_ids:
        return set(active_ids)
    if state is None:
        return set()
    return coverage_open_ids(plan, state)


def live_active_triage_issue_ids(
    plan: PlanModel,
    state: StateModel | None = None,
) -> set[str]:
    """Return frozen triage IDs that are still open review issues in state."""
    frozen_ids = active_triage_issue_ids(plan, state)
    if state is None or not frozen_ids:
        return frozen_ids
    return frozen_ids & open_review_ids(state)


def ensure_active_triage_issue_ids(plan: PlanModel, state: StateModel) -> list[str]:
    """Freeze the current triage issue set for validation across stage reruns."""
    meta = ensure_triage_meta(plan)
    active_ids = sorted(coverage_open_ids(plan, state))
    meta[_ACTIVE_TRIAGE_ISSUE_IDS_KEY] = active_ids
    meta.pop(_UNDISPOSITIONED_TRIAGE_ISSUES_KEY, None)
    meta.pop(_UNDISPOSITIONED_TRIAGE_COUNT_KEY, None)
    return active_ids


def clear_active_triage_issue_tracking(meta: dict[str, object]) -> None:
    """Clear frozen triage coverage metadata after successful completion."""
    meta.pop(_ACTIVE_TRIAGE_ISSUE_IDS_KEY, None)
    meta.pop(_UNDISPOSITIONED_TRIAGE_ISSUES_KEY, None)
    meta.pop(_UNDISPOSITIONED_TRIAGE_COUNT_KEY, None)


def undispositioned_triage_issue_ids(
    plan: PlanModel,
    state: StateModel | None = None,
) -> list[str]:
    """Return frozen triage issues still lacking cluster/skip/dismiss coverage."""
    target_ids = live_active_triage_issue_ids(plan, state)
    if not target_ids:
        return []
    covered_ids: set[str] = set()
    for cluster in ensure_cluster_map(plan).values():
        if cluster.get("auto"):
            continue
        covered_ids.update(cluster_issue_ids(cluster))
    covered_ids.update(
        issue_id for issue_id in ensure_skipped_map(plan) if isinstance(issue_id, str)
    )
    covered_ids.update(
        normalized_issue_id_list(ensure_triage_meta(plan).get("dismissed_ids"))
    )
    return sorted(issue_id for issue_id in target_ids if issue_id not in covered_ids)


def sync_undispositioned_triage_meta(
    plan: PlanModel,
    state: StateModel | None = None,
) -> list[str]:
    """Persist the current undispositioned triage issue set for recovery UX."""
    meta = ensure_triage_meta(plan)
    missing = undispositioned_triage_issue_ids(plan, state)
    if missing:
        meta[_UNDISPOSITIONED_TRIAGE_ISSUES_KEY] = missing
        meta[_UNDISPOSITIONED_TRIAGE_COUNT_KEY] = len(missing)
    else:
        meta.pop(_UNDISPOSITIONED_TRIAGE_ISSUES_KEY, None)
        meta.pop(_UNDISPOSITIONED_TRIAGE_COUNT_KEY, None)
    return missing


def triage_coverage(
    plan: PlanModel,
    open_review_ids: set[str] | None = None,
) -> tuple[int, int, dict[str, Cluster]]:
    """Return (organized, total, clusters) for review issues in triage."""
    clusters = ensure_cluster_map(plan)
    all_cluster_ids: set[str] = set()
    for cluster in clusters.values():
        all_cluster_ids.update(cluster_issue_ids(cluster))
    review_ids = list(open_review_ids) if open_review_ids is not None else plan_review_ids(plan)
    organized = sum(1 for fid in review_ids if fid in all_cluster_ids)
    return organized, len(review_ids), clusters


def manual_clusters_with_issues(plan: PlanModel) -> list[str]:
    """Return manual clusters that currently own at least one issue."""
    return [
        name
        for name, cluster in ensure_cluster_map(plan).items()
        if cluster_issue_ids(cluster) and not cluster.get("auto")
    ]


def find_cluster_for(fid: str, clusters: dict[str, Cluster]) -> str | None:
    """Return the owning cluster name for an issue ID, if any."""
    for name, cluster in clusters.items():
        if fid in cluster_issue_ids(cluster):
            return name
    return None


__all__ = [
    "active_triage_issue_ids",
    "clear_active_triage_issue_tracking",
    "cluster_issue_ids",
    "coverage_open_ids",
    "ensure_active_triage_issue_ids",
    "find_cluster_for",
    "has_open_review_issues",
    "live_active_triage_issue_ids",
    "manual_clusters_with_issues",
    "open_review_ids_from_state",
    "plan_review_ids",
    "sync_undispositioned_triage_meta",
    "triage_coverage",
    "undispositioned_triage_issue_ids",
]
