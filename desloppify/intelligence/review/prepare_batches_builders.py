"""Top-level batch building APIs for holistic review preparation."""

from __future__ import annotations

from pathlib import Path

from .prepare_batches_collectors import _DIMENSION_FILE_MAPPING, _FILE_COLLECTORS
from .prepare_batches_core import (
    _collect_files_from_batches,
    _ensure_holistic_context,
    _normalize_file_path,
)


def build_investigation_batches(
    holistic_ctx,
    lang: object,
    *,
    repo_root: Path | None = None,
    max_files_per_batch: int | None = None,
) -> list[dict]:
    """Build one batch per dimension from holistic context."""
    ctx = _ensure_holistic_context(holistic_ctx)
    del lang
    del repo_root

    file_cache: dict[str, list[str]] = {}
    batches: list[dict] = []

    for dimension, collector_key in _DIMENSION_FILE_MAPPING.items():
        if collector_key not in file_cache:
            collector = _FILE_COLLECTORS[collector_key]
            file_cache[collector_key] = collector(
                ctx,
                max_files=max_files_per_batch,
            )

        files = file_cache[collector_key]
        if not files:
            continue

        batches.append(
            {
                "name": dimension,
                "dimensions": [dimension],
                "files_to_read": files,
                "why": f"seed files for {dimension} review",
            }
        )

    return batches


def filter_batches_to_dimensions(
    batches: list[dict],
    dimensions: list[str],
    *,
    fallback_max_files: int | None = 80,
) -> list[dict]:
    """Keep only batches whose dimension is in the active set."""
    selected = [dimension for dimension in dimensions if isinstance(dimension, str) and dimension]
    if not selected:
        return []
    selected_set = set(selected)
    filtered: list[dict] = []
    covered: set[str] = set()
    for batch in batches:
        batch_dims = [dim for dim in batch.get("dimensions", []) if dim in selected_set]
        if not batch_dims:
            continue
        filtered.append({**batch, "dimensions": batch_dims})
        covered.update(batch_dims)

    missing = [dim for dim in selected if dim not in covered]
    if not missing:
        return filtered

    max_files = fallback_max_files if isinstance(fallback_max_files, int) else None
    if isinstance(max_files, int) and max_files <= 0:
        max_files = None
    fallback_files = _collect_files_from_batches(
        filtered or batches,
        max_files=max_files,
    )
    if not fallback_files:
        return filtered

    for dim in missing:
        filtered.append(
            {
                "name": dim,
                "dimensions": [dim],
                "files_to_read": fallback_files,
                "why": f"no direct batch mapping for {dim}; using representative files",
            }
        )
    return filtered


def batch_concerns(
    concerns: list,
    *,
    max_files: int | None = None,
    active_dimensions: list[str] | None = None,
) -> dict | None:
    """Build investigation batch from mechanical concern signals."""
    del active_dimensions
    if not concerns:
        return None

    types = sorted({concern.type for concern in concerns if concern.type})
    why_parts = ["mechanical detectors identified structural patterns needing judgment"]
    if types:
        why_parts.append(f"concern types: {', '.join(types)}")

    files: list[str] = []
    seen: set[str] = set()
    concern_signals: list[dict[str, object]] = []
    for concern in concerns:
        candidate = _normalize_file_path(getattr(concern, "file", ""))
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        files.append(candidate)

        evidence_raw = getattr(concern, "evidence", ())
        evidence = [
            str(entry).strip()
            for entry in evidence_raw
            if isinstance(entry, str) and entry.strip()
        ][:4]
        summary = str(getattr(concern, "summary", "")).strip()
        question = str(getattr(concern, "question", "")).strip()
        concern_type = str(getattr(concern, "type", "")).strip()
        fingerprint = str(getattr(concern, "fingerprint", "")).strip()
        source_issues = tuple(
            str(sid)
            for sid in getattr(concern, "source_issues", ())
            if isinstance(sid, str) and sid
        )
        signal: dict[str, object] = {
            "type": concern_type or "design_concern",
            "file": candidate,
            "summary": summary or "Mechanical concern requires subjective judgment",
            "question": question or "Is this pattern intentional or debt?",
            "evidence": evidence,
        }
        if fingerprint:
            signal["fingerprint"] = fingerprint
        if source_issues:
            signal["finding_ids"] = list(source_issues)
        concern_signals.append(signal)

    total_candidate_files = len(files)
    if (
        max_files is not None
        and isinstance(max_files, int)
        and max_files > 0
        and total_candidate_files > max_files
    ):
        files = files[:max_files]
        why_parts.append(
            f"truncated to {max_files} files from {total_candidate_files} candidates"
        )

    # Build per-detector judgment finding counts by extracting the detector name
    # from each source issue ID (format: "detector::file::detail").
    detector_counts: dict[str, int] = {}
    seen_source_ids: set[str] = set()
    for concern in concerns:
        for sid in getattr(concern, "source_issues", ()):
            sid_str = str(sid)
            if sid_str in seen_source_ids:
                continue
            seen_source_ids.add(sid_str)
            detector = sid_str.split("::", 1)[0] if "::" in sid_str else ""
            if detector:
                detector_counts[detector] = detector_counts.get(detector, 0) + 1

    result: dict[str, object] = {
        "name": "design_coherence",
        "dimensions": ["design_coherence"],
        "files_to_read": files,
        "why": "; ".join(why_parts),
        "total_candidate_files": total_candidate_files,
        "concern_signals": concern_signals,
        "concern_signal_count": len(concern_signals),
    }
    if detector_counts:
        result["judgment_finding_counts"] = detector_counts
    return result


# Mechanical detectors → subjective dimensions they provide evidence for.
# Mirrors _DETECTOR_SUBJECTIVE_DIMENSIONS in engine/_state/merge.py.
_DETECTOR_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "structural": ("design_coherence", "abstraction_fitness"),
    "smells": ("design_coherence", "error_consistency"),
    "global_mutable_config": ("initialization_coupling",),
    "coupling": ("cross_module_architecture",),
    "layer_violation": ("cross_module_architecture",),
    "private_imports": ("cross_module_architecture",),
    "dupes": ("convention_outlier",),
    "boilerplate_duplication": ("convention_outlier",),
    "naming": ("convention_outlier", "naming_quality"),
    "flat_dirs": ("package_organization",),
    "orphaned": ("design_coherence",),
    "uncalled_functions": ("design_coherence",),
    "responsibility_cohesion": ("design_coherence", "abstraction_fitness"),
    "cycles": ("cross_module_architecture", "dependency_health"),
    "dict_keys": ("type_safety",),
    "props": ("abstraction_fitness",),
    "signature": ("convention_outlier",),
    "security": ("error_consistency",),
    "facade": ("abstraction_fitness",),
    "patterns": ("convention_outlier",),
    "react": ("design_coherence",),
    "single_use": ("abstraction_fitness",),
}

# Invert to dimension → set of detectors.
_DIMENSION_DETECTORS: dict[str, set[str]] = {}
for _det, _dims in _DETECTOR_DIMENSIONS.items():
    for _dim in _dims:
        _DIMENSION_DETECTORS.setdefault(_dim, set()).add(_det)


def annotate_batches_with_judgment_findings(
    batches: list[dict],
    state: dict,
) -> None:
    """Add per-dimension judgment_finding_counts to batches that lack them.

    For each batch, look at its dimension(s), find which detectors map to those
    dimensions, count open judgment findings per detector from state, and inject
    ``judgment_finding_counts`` so the prompt renderer can show CLI exploration
    commands.  Batches that already have ``judgment_finding_counts`` (e.g. the
    design_coherence concern batch) are left untouched.
    """
    from desloppify.base.registry import JUDGMENT_DETECTORS

    issues = state.get("issues")
    if not isinstance(issues, dict):
        return

    # Count open judgment findings per detector once.
    global_detector_counts: dict[str, int] = {}
    for issue in issues.values():
        if not isinstance(issue, dict):
            continue
        status = str(issue.get("status", "")).strip()
        if status not in ("open", "reopened"):
            continue
        detector = str(issue.get("detector", "")).strip()
        if detector and detector in JUDGMENT_DETECTORS:
            global_detector_counts[detector] = global_detector_counts.get(detector, 0) + 1

    if not global_detector_counts:
        return

    for batch in batches:
        if batch.get("judgment_finding_counts"):
            continue
        dims = batch.get("dimensions", [])
        if not isinstance(dims, list):
            continue
        # Collect detectors relevant to this batch's dimensions.
        relevant_detectors: set[str] = set()
        for dim in dims:
            relevant_detectors.update(_DIMENSION_DETECTORS.get(dim, ()))
        if not relevant_detectors:
            continue
        counts = {
            det: count
            for det, count in global_detector_counts.items()
            if det in relevant_detectors
        }
        if counts:
            batch["judgment_finding_counts"] = counts


__all__ = [
    "annotate_batches_with_judgment_findings",
    "batch_concerns",
    "build_investigation_batches",
    "filter_batches_to_dimensions",
]
