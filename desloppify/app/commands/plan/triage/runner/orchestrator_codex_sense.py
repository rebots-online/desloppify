"""Sense-check parallel codex execution helpers."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from desloppify.base.discovery.file_paths import safe_write_text
from desloppify.base.output.terminal import colorize
from desloppify.engine.plan import load_policy, render_policy_block

from ..helpers import manual_clusters_with_issues
from .codex_runner import _output_file_has_text, run_triage_stage
from .orchestrator_codex_parallel import run_parallel_batches
from .stage_prompts import (
    build_sense_check_content_prompt,
    build_sense_check_structure_prompt,
)


def _noop_log(_msg: str) -> None:
    """Default run-log sink when the caller doesn't provide one."""


def run_sense_check(
    *,
    plan: dict,
    repo_root: Path,
    prompts_dir: Path,
    output_dir: Path,
    logs_dir: Path,
    timeout_seconds: int,
    dry_run: bool = False,
    append_run_log=None,
) -> tuple[bool, str]:
    """Run sense-check via parallel codex subprocess batches."""
    _log = append_run_log or _noop_log

    clusters = manual_clusters_with_issues(plan)
    total_content = len(clusters)
    total = total_content + 1
    print(colorize(f"\n  Sense-check: {total_content} content batches + 1 structure batch.", "bold"))
    _log(f"sense-check-parallel content_batches={total_content}")

    policy = load_policy()
    policy_text = render_policy_block(policy)

    tasks: dict[int, object] = {}
    batch_meta: list[tuple[str, Path]] = []

    for i, cluster_name in enumerate(clusters):
        prompt = build_sense_check_content_prompt(
            cluster_name=cluster_name, plan=plan, repo_root=repo_root,
            policy_block=policy_text,
        )
        prompt_file = prompts_dir / f"sense_check_content_{i}.md"
        safe_write_text(prompt_file, prompt)

        output_file = output_dir / f"sense_check_content_{i}.raw.txt"
        log_file = logs_dir / f"sense_check_content_{i}.log"
        batch_meta.append((f"content:{cluster_name}", output_file))

        if not dry_run:
            tasks[i] = partial(
                run_triage_stage,
                prompt=prompt,
                repo_root=repo_root,
                output_file=output_file,
                log_file=log_file,
                timeout_seconds=timeout_seconds,
                validate_output_fn=_output_file_has_text,
            )
        print(colorize(f"    Content batch {i + 1}: {cluster_name}", "dim"))
        _log(f"sense-check-content batch={i + 1} cluster={cluster_name}")

    structure_idx = total_content
    structure_prompt = build_sense_check_structure_prompt(plan=plan, repo_root=repo_root)
    prompt_file = prompts_dir / "sense_check_structure.md"
    safe_write_text(prompt_file, structure_prompt)

    structure_output = output_dir / "sense_check_structure.raw.txt"
    structure_log = logs_dir / "sense_check_structure.log"
    batch_meta.append(("structure", structure_output))

    if not dry_run:
        tasks[structure_idx] = partial(
            run_triage_stage,
            prompt=structure_prompt,
            repo_root=repo_root,
            output_file=structure_output,
            log_file=structure_log,
            timeout_seconds=timeout_seconds,
            validate_output_fn=_output_file_has_text,
        )
    print(colorize("    Structure batch: global dependency check", "dim"))
    _log("sense-check-structure batch=global")

    if dry_run:
        print(colorize("  [dry-run] Would execute parallel sense-check batches.", "dim"))
        return True, ""

    def _batch_label(idx: int) -> str:
        if idx < len(batch_meta):
            return batch_meta[idx][0]
        return f"batch-{idx}"

    failures = run_parallel_batches(
        tasks=tasks,
        stage_label="Sense-check",
        batch_label_fn=_batch_label,
        append_run_log=_log,
        heartbeat_seconds=15.0,
    )

    if failures:
        print(colorize(f"  Sense-check: {len(failures)} batch(es) failed: {failures}", "red"))
        _log(f"sense-check-parallel-failed failures={failures}")
        return False, ""

    parts: list[str] = []
    for label, output_file in batch_meta:
        content = ""
        if output_file.exists():
            try:
                content = output_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                content = "(output missing)"
        if not content:
            content = "(no output)"
        parts.append(f"## {label}\n\n{content}")

    merged = "\n\n---\n\n".join(parts)
    print(colorize(f"  Sense-check: merged {total} batch outputs ({len(merged)} chars).", "green"))
    _log(f"sense-check-parallel-done merged_chars={len(merged)}")
    return True, merged


__all__ = ["run_sense_check"]
