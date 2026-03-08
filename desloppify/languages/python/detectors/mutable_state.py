"""Compatibility facade for mutable-state detector helpers."""

from __future__ import annotations

from desloppify.languages.python.detectors.mutable_state_ast import (
    _collect_module_level_mutables,
    _detect_in_module,
    _find_mutations_in_functions,
    _is_mutable_init,
    _is_optional_annotation,
    _is_upper_case,
)
from desloppify.languages.python.detectors.mutable_state_scan import (
    _detect_stale_imports,
    detect_global_mutable_config,
)

__all__ = [
    "_collect_module_level_mutables",
    "_detect_in_module",
    "_detect_stale_imports",
    "_find_mutations_in_functions",
    "_is_mutable_init",
    "_is_optional_annotation",
    "_is_upper_case",
    "detect_global_mutable_config",
]
