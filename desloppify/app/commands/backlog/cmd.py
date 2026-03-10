"""backlog command: show open backlog items outside the execution queue."""

from __future__ import annotations

import argparse

from desloppify.app.commands.helpers.lang import resolve_lang
from desloppify.app.commands.helpers.query import write_query
from desloppify.app.commands.helpers.runtime import command_runtime
from desloppify.app.commands.helpers.state import require_completed_scan
from desloppify.base.output.terminal import colorize
from desloppify.base.tooling import check_config_staleness
from desloppify.engine.plan_state import load_plan
from desloppify.engine.planning.queue_policy import build_backlog_queue

from desloppify.app.commands.next.queue_flow import build_and_render_queue


def cmd_backlog(args: argparse.Namespace) -> None:
    """Show backlog items that are not currently part of the execution queue."""
    runtime = command_runtime(args)
    state = runtime.state
    config = runtime.config
    if not require_completed_scan(state):
        return

    config_warning = check_config_staleness(config)
    if config_warning:
        print(colorize(f"  {config_warning}", "yellow"))

    build_and_render_queue(
        args,
        state,
        config,
        resolve_lang_fn=resolve_lang,
        load_plan_fn=load_plan,
        build_work_queue_fn=build_backlog_queue,
        write_query_fn=write_query,
        command_name="backlog",
        show_plan_context=False,
        collapse_plan_clusters=False,
        show_execution_prompt=False,
    )


__all__ = ["cmd_backlog"]
