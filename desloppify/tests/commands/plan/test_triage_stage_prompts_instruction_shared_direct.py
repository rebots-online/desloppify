"""Direct tests for shared triage prompt instruction text helpers."""

from __future__ import annotations

import desloppify.app.commands.plan.triage.runner.stage_prompts_instruction_shared as shared_mod


def test_triage_prompt_preamble_output_only_vs_self_record() -> None:
    output_only = shared_mod.triage_prompt_preamble("output_only")
    self_record = shared_mod.triage_prompt_preamble("self_record")

    assert "Output Contract" in output_only
    assert "Do NOT run any `desloppify` commands." in output_only
    assert "Use the desloppify CLI to record your work." in self_record
    assert "Only run commands for YOUR stage" in self_record


def test_render_cli_reference_substitutes_cli_command() -> None:
    rendered = shared_mod.render_cli_reference(cli_command="dx")
    assert "dx plan triage --stage observe" in rendered
    assert "dx plan cluster create" in rendered
    assert "dx plan skip --permanent" in rendered


def test_shared_stage_constants_cover_all_expected_stages() -> None:
    assert shared_mod._STAGES == (
        "observe",
        "reflect",
        "organize",
        "enrich",
        "sense-check",
    )
