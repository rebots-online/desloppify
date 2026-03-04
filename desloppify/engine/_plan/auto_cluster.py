"""Auto-clustering algorithm — groups issues into task clusters."""

from __future__ import annotations

from desloppify.base.config import DEFAULT_TARGET_STRICT_SCORE
from desloppify.engine._plan.auto_cluster_sync import (
    prune_stale_clusters as _prune_stale_clusters,
    sync_issue_clusters as _sync_issue_clusters,
    sync_subjective_clusters as _sync_subjective_clusters,
)
from desloppify.engine._plan.cluster_strategy import (
    cluster_name_from_key as _cluster_name_from_key,
    generate_action as _generate_action,
    grouping_key as _grouping_key,
    strip_guidance_examples as _strip_guidance_examples,
)
from desloppify.engine._plan.schema import PlanModel, ensure_plan_defaults
from desloppify.engine._plan.subjective_policy import SubjectiveVisibility
from desloppify.engine._state.schema import StateModel, utc_now

AUTO_PREFIX = "auto/"


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def _repair_ghost_cluster_refs(plan: PlanModel, now: str) -> int:
    """Clear override cluster refs that point to non-existent clusters."""
    clusters = plan.get("clusters", {})
    overrides = plan.get("overrides", {})
    repaired = 0
    for override in overrides.values():
        cluster_name = override.get("cluster")
        if cluster_name and cluster_name not in clusters:
            override["cluster"] = None
            override["updated_at"] = now
            repaired += 1
    return repaired


def auto_cluster_issues(
    plan: PlanModel,
    state: StateModel,
    *,
    target_strict: float = DEFAULT_TARGET_STRICT_SCORE,
    policy: SubjectiveVisibility | None = None,
    cycle_just_completed: bool = False,
) -> int:
    """Regenerate auto-clusters from current open issues.

    Returns count of changes made (clusters created, updated, or deleted).
    """
    ensure_plan_defaults(plan)

    issues = state.get("issues", {})
    clusters = plan.get("clusters", {})

    # Map existing auto-clusters by cluster_key
    existing_by_key: dict[str, str] = {}  # cluster_key → cluster_name
    for name, cluster in list(clusters.items()):
        if cluster.get("auto"):
            ck = cluster.get("cluster_key", "")
            if ck:
                existing_by_key[ck] = name

    now = utc_now()
    active_auto_keys: set[str] = set()
    changes = 0

    changes += _sync_issue_clusters(
        plan, issues, clusters, existing_by_key, active_auto_keys, now,
    )
    changes += _sync_subjective_clusters(
        plan, state, issues, clusters, existing_by_key, active_auto_keys, now,
        target_strict=target_strict,
        policy=policy,
        cycle_just_completed=cycle_just_completed,
    )
    changes += _prune_stale_clusters(
        plan, issues, clusters, active_auto_keys, now,
    )
    changes += _repair_ghost_cluster_refs(plan, now)

    plan["updated"] = now
    return changes


__all__ = [
    "AUTO_PREFIX",
    "auto_cluster_issues",
]
