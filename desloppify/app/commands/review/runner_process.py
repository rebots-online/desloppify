"""Compatibility wrapper for shared codex batch runner helpers."""

from __future__ import annotations

from pathlib import Path

from desloppify.app.commands.runner.codex_batch import (
    CodexBatchRunnerDeps,
    FollowupScanDeps,
    codex_batch_command as _shared_codex_batch_command,
    run_codex_batch as _shared_run_codex_batch,
    run_followup_scan as _shared_run_followup_scan,
)


def codex_batch_command(*, prompt: str, repo_root: Path, output_file: Path) -> list[str]:
    """Build one codex exec command line for a batch prompt."""
    return _shared_codex_batch_command(
        prompt=prompt,
        repo_root=repo_root,
        output_file=output_file,
    )


def run_codex_batch(
    *,
    prompt: str,
    repo_root: Path,
    output_file: Path,
    log_file: Path,
    deps: CodexBatchRunnerDeps,
    codex_batch_command_fn=None,
) -> int:
    """Execute one codex batch and return a stable CLI-style status code."""
    return _shared_run_codex_batch(
        prompt=prompt,
        repo_root=repo_root,
        output_file=output_file,
        log_file=log_file,
        deps=deps,
        codex_batch_command_fn=codex_batch_command_fn or codex_batch_command,
    )


def run_followup_scan(
    *,
    lang_name: str,
    scan_path: str,
    deps: FollowupScanDeps,
    force_queue_bypass: bool = False,
) -> int:
    """Run a follow-up scan and return a non-zero status when it fails."""
    return _shared_run_followup_scan(
        lang_name=lang_name,
        scan_path=scan_path,
        deps=deps,
        force_queue_bypass=force_queue_bypass,
    )


__all__ = [
    "CodexBatchRunnerDeps",
    "FollowupScanDeps",
    "codex_batch_command",
    "run_codex_batch",
    "run_followup_scan",
]
