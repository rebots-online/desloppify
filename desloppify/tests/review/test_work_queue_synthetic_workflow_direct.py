"""Direct coverage tests for synthetic workflow work-queue item builders."""

from __future__ import annotations

from types import SimpleNamespace

import desloppify.engine._work_queue.synthetic_workflow as workflow_mod


def test_build_score_checkpoint_item_returns_none_when_not_queued() -> None:
    assert workflow_mod.build_score_checkpoint_item({"queue_order": []}, {}) is None


def test_build_score_checkpoint_item_includes_strict_delta(monkeypatch) -> None:
    from desloppify.engine._plan.constants import WORKFLOW_SCORE_CHECKPOINT_ID

    monkeypatch.setattr(
        "desloppify.state.score_snapshot",
        lambda _state: SimpleNamespace(strict=76.4),
    )
    plan = {
        "queue_order": [WORKFLOW_SCORE_CHECKPOINT_ID],
        "plan_start_scores": {"strict": 75.0},
    }

    item = workflow_mod.build_score_checkpoint_item(plan, {})

    assert item is not None
    assert item["id"] == WORKFLOW_SCORE_CHECKPOINT_ID
    assert item["kind"] == "workflow_action"
    assert item["summary"].endswith("76.4/100 (+1.4)")
    assert item["detail"]["delta"] == 1.4


def test_build_create_plan_and_import_scores_items() -> None:
    from desloppify.engine._plan.constants import (
        WORKFLOW_CREATE_PLAN_ID,
        WORKFLOW_IMPORT_SCORES_ID,
    )

    create_item = workflow_mod.build_create_plan_item(
        {"queue_order": [WORKFLOW_CREATE_PLAN_ID]}
    )
    assert create_item is not None
    assert create_item["id"] == WORKFLOW_CREATE_PLAN_ID
    assert "Create prioritized plan" in create_item["summary"]

    import_item = workflow_mod.build_import_scores_item(
        {"queue_order": [WORKFLOW_IMPORT_SCORES_ID]},
        {},
    )
    assert import_item is not None
    assert import_item["id"] == WORKFLOW_IMPORT_SCORES_ID
    assert "untrusted source" in import_item["detail"]["explanation"]


def test_build_communicate_score_item_formats_command_and_delta(monkeypatch) -> None:
    from desloppify.engine._plan.constants import WORKFLOW_COMMUNICATE_SCORE_ID

    monkeypatch.setattr(
        "desloppify.state.score_snapshot",
        lambda _state: SimpleNamespace(strict=80.0),
    )
    plan = {
        "queue_order": [WORKFLOW_COMMUNICATE_SCORE_ID],
        "plan_start_scores": {"strict": 80.0},
    }

    item = workflow_mod.build_communicate_score_item(plan, {})

    assert item is not None
    assert item["id"] == WORKFLOW_COMMUNICATE_SCORE_ID
    assert item["summary"].endswith("80.0/100")
    assert item["detail"]["delta"] == 0.0
    assert WORKFLOW_COMMUNICATE_SCORE_ID in item["primary_command"]
