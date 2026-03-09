"""Direct tests for plan override helper modules."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

import desloppify.app.commands.plan.override_io as override_io_mod
import desloppify.app.commands.plan.override_misc as override_misc_mod
import desloppify.app.commands.plan.override_resolve_cmd as override_resolve_cmd_mod
import desloppify.app.commands.plan.override_resolve_helpers as resolve_helpers_mod
import desloppify.app.commands.plan.override_skip as override_skip_mod
from desloppify.base.exception_sets import CommandError


def test_override_io_snapshot_restore_and_plan_file_resolution(monkeypatch, tmp_path) -> None:
    assert override_io_mod._plan_file_for_state(None) is None

    state_path = tmp_path / "state.json"
    expected_plan_path = tmp_path / "state.plan.json"
    monkeypatch.setattr(override_io_mod, "plan_path_for_state", lambda _path: expected_plan_path)
    assert override_io_mod._plan_file_for_state(state_path) == expected_plan_path

    target = tmp_path / "sample.txt"
    assert override_io_mod._snapshot_file(target) is None

    target.write_text("before", encoding="utf-8")
    snap = override_io_mod._snapshot_file(target)
    assert snap == "before"

    override_io_mod._restore_file_snapshot(target, "after")
    assert target.read_text(encoding="utf-8") == "after"

    override_io_mod._restore_file_snapshot(target, None)
    assert not target.exists()


def test_override_resolve_helpers_cover_synthetic_split_and_blocked_stages(capsys) -> None:
    synthetic, remaining = resolve_helpers_mod.resolve_synthetic_ids(
        ["triage::reflect", "workflow::create-plan", "unused::src/a.py::X"]
    )
    assert synthetic == ["triage::reflect", "workflow::create-plan"]
    assert remaining == ["unused::src/a.py::X"]

    plan = {
        "queue_order": ["triage::observe", "triage::reflect", "triage::organize"],
        "epic_triage_meta": {"triage_stages": {}},
    }
    blocked = resolve_helpers_mod.blocked_triage_stages(plan)
    assert blocked["triage::reflect"] == ["triage::observe"]
    assert blocked["triage::organize"] == ["triage::reflect"]

    state = {
        "issues": {
            "i1": {"status": "open", "summary": "First", "detector": "review"},
            "i2": {"status": "open", "summary": "Second", "detector": "review"},
        }
    }
    cluster_plan = {"clusters": {"small": {"issue_ids": ["i1", "i2"]}}}
    blocked_cluster = resolve_helpers_mod.check_cluster_guard(
        ["small"], cluster_plan, state
    )
    assert blocked_cluster is True
    out = capsys.readouterr().out
    assert "mark them done individually first" in out


def test_override_resolve_cmd_confirm_requires_note(capsys) -> None:
    args = argparse.Namespace(
        patterns=["unused::src/a.py::X"],
        attest=None,
        note=None,
        confirm=True,
        force_resolve=False,
        state=None,
        lang=None,
        path=".",
        exclude=None,
    )
    override_resolve_cmd_mod.cmd_plan_resolve(args)
    out = capsys.readouterr().out
    assert "--confirm requires --note" in out


def test_override_resolve_cmd_handles_synthetic_only_resolution(monkeypatch, capsys) -> None:
    plan = {"queue_order": ["triage::observe"], "clusters": {}}
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(override_resolve_cmd_mod, "load_plan", lambda: plan)
    monkeypatch.setattr(override_resolve_cmd_mod, "blocked_triage_stages", lambda _plan: {})
    monkeypatch.setattr(
        override_resolve_cmd_mod,
        "purge_ids",
        lambda _plan, ids: calls.append(("purge", list(ids))),
    )
    monkeypatch.setattr(
        override_resolve_cmd_mod,
        "auto_complete_steps",
        lambda _plan: ["step complete"],
    )
    monkeypatch.setattr(
        override_resolve_cmd_mod,
        "append_log_entry",
        lambda *_a, **_k: calls.append(("log", [])),
    )
    monkeypatch.setattr(override_resolve_cmd_mod, "save_plan", lambda *_a, **_k: None)

    args = argparse.Namespace(
        patterns=["triage::observe"],
        attest=None,
        note=None,
        confirm=False,
        force_resolve=False,
        state=None,
        lang=None,
        path=".",
        exclude=None,
    )
    override_resolve_cmd_mod.cmd_plan_resolve(args)
    out = capsys.readouterr().out
    assert "Resolved: triage::observe" in out
    assert ("purge", ["triage::observe"]) in calls


def test_override_misc_focus_and_scan_gate_paths(monkeypatch, capsys) -> None:
    plan = {
        "clusters": {"alpha": {}},
        "active_cluster": None,
        "scan_count_at_plan_start": 3,
        "scan_gate_skipped": False,
    }
    monkeypatch.setattr(override_misc_mod, "load_plan", lambda: plan)
    monkeypatch.setattr(override_misc_mod, "append_log_entry", lambda *_a, **_k: None)
    monkeypatch.setattr(override_misc_mod, "save_plan", lambda *_a, **_k: None)
    monkeypatch.setattr(override_misc_mod, "set_focus", lambda p, name: p.update({"active_cluster": name}))
    monkeypatch.setattr(override_misc_mod, "clear_focus", lambda p: p.update({"active_cluster": None}))

    override_misc_mod.cmd_plan_focus(argparse.Namespace(clear=False, cluster_name="alpha"))
    out_focus = capsys.readouterr().out
    assert "Focused on: alpha" in out_focus
    assert plan["active_cluster"] == "alpha"

    override_misc_mod.cmd_plan_focus(argparse.Namespace(clear=True, cluster_name=None))
    out_clear = capsys.readouterr().out
    assert "Focus cleared" in out_clear

    monkeypatch.setattr(override_misc_mod, "state_path", lambda _args: Path("state.json"))
    monkeypatch.setattr(override_misc_mod.state_mod, "load_state", lambda _path: {"scan_count": 3})

    override_misc_mod.cmd_plan_scan_gate(argparse.Namespace(skip=False, note=None))
    out_blocked = capsys.readouterr().out
    assert "Scan gate: BLOCKED" in out_blocked

    override_misc_mod.cmd_plan_scan_gate(argparse.Namespace(skip=True, note="too short"))
    out_short = capsys.readouterr().out
    assert "requires --note with at least 50 chars" in out_short

    long_note = (
        "Skipping scan gate in this direct test because we are verifying "
        "guard behavior and not advancing a real cycle."
    )
    override_misc_mod.cmd_plan_scan_gate(argparse.Namespace(skip=True, note=long_note))
    out_skip = capsys.readouterr().out
    assert "marked as satisfied" in out_skip
    assert plan["scan_gate_skipped"] is True


def test_override_skip_helpers_and_commands(monkeypatch, capsys) -> None:
    monkeypatch.setattr(override_skip_mod, "skip_kind_requires_attestation", lambda _kind: True)
    monkeypatch.setattr(
        override_skip_mod,
        "validate_attestation",
        lambda _att, **_kwargs: False,
    )
    assert (
        override_skip_mod._validate_skip_requirements(
            kind="permanent",
            attestation=None,
            note="x",
        )
        is False
    )

    monkeypatch.setattr(override_skip_mod, "skip_kind_state_status", lambda _kind: None)
    assert (
        override_skip_mod._apply_state_skip_resolution(
            kind="temporary",
            state_file=None,
            issue_ids=["i1"],
            note=None,
            attestation=None,
        )
        is None
    )
    monkeypatch.setattr(override_skip_mod, "skip_kind_requires_attestation", lambda _kind: False)

    runtime = SimpleNamespace(
        state={"last_scan": "2026-03-01T00:00:00+00:00", "scan_count": 2, "issues": {}},
        state_path=None,
    )
    monkeypatch.setattr(override_skip_mod, "command_runtime", lambda _args: runtime)
    monkeypatch.setattr(override_skip_mod, "require_completed_scan", lambda _state: True)
    monkeypatch.setattr(override_skip_mod, "load_plan", lambda _plan_file=None: {"queue_order": []})
    monkeypatch.setattr(
        override_skip_mod,
        "resolve_ids_from_patterns",
        lambda *_a, **_k: [f"i{n}" for n in range(6)],
    )

    with pytest.raises(CommandError):
        override_skip_mod.cmd_plan_skip(
            argparse.Namespace(
                patterns=["review::*"],
                reason=None,
                review_after=None,
                permanent=False,
                false_positive=False,
                note=None,
                attest=None,
                confirm=False,
            )
        )

    plan = {"queue_order": ["i1"], "skipped": {"i1": {"kind": "temporary"}}}
    monkeypatch.setattr(override_skip_mod, "load_plan", lambda _plan_file=None: plan)
    monkeypatch.setattr(
        override_skip_mod,
        "resolve_ids_from_patterns",
        lambda *_a, **_k: ["i1"],
    )
    monkeypatch.setattr(
        override_skip_mod,
        "unskip_items",
        lambda *_a, **_k: (1, ["i1"], []),
    )
    monkeypatch.setattr(
        override_skip_mod.state_mod,
        "load_state",
        lambda _path: {"issues": {"i1": {"status": "wontfix"}}},
    )
    monkeypatch.setattr(
        override_skip_mod.state_mod,
        "resolve_issues",
        lambda _state, fid, _status: [fid],
    )
    monkeypatch.setattr(override_skip_mod, "append_log_entry", lambda *_a, **_k: None)
    monkeypatch.setattr(
        override_skip_mod,
        "save_plan_state_transactional",
        lambda **_kwargs: None,
    )

    override_skip_mod.cmd_plan_unskip(
        argparse.Namespace(patterns=["i1"], force=False)
    )
    out = capsys.readouterr().out
    assert "Unskipped 1 item(s)" in out


def test_cmd_plan_skip_invalid_permanent_skip_exits_nonzero(monkeypatch) -> None:
    runtime = SimpleNamespace(
        state={"last_scan": "2026-03-01T00:00:00+00:00", "scan_count": 2, "issues": {}},
        state_path=None,
    )
    monkeypatch.setattr(override_skip_mod, "command_runtime", lambda _args: runtime)
    monkeypatch.setattr(override_skip_mod, "require_completed_scan", lambda _state: True)

    with pytest.raises(CommandError) as excinfo:
        override_skip_mod.cmd_plan_skip(
            argparse.Namespace(
                patterns=["review::foo::deadbeef"],
                reason=None,
                review_after=None,
                permanent=True,
                false_positive=False,
                note="Reviewed as intentional architecture debt with a concrete justification.",
                attest="I reviewed this and will suppress it.",
                confirm=False,
            )
        )

    assert excinfo.value.exit_code == 2


def test_validate_skip_requirements_accepts_review_attestation() -> None:
    assert override_skip_mod._validate_skip_requirements(
        kind="permanent",
        attestation=(
            "I have reviewed this triage skip against the code and I am not gaming "
            "the score by suppressing a real defect."
        ),
        note="Reviewed and intentionally accepted for now.",
    )
