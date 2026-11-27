# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer research, implementation, feedback, and Workgroup lifecycle subflow."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision

from ..agents.checker import CheckerAgent
from ..agents.explorer import ExplorerAgent

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


async def run_exploration_subflow(
    workflow: "DefaultWorkflow",
    workspace_id: str,
    task_revision: TaskRevision,
    *,
    experiment_results: asyncio.Queue[str],
    submit_to_experiment: Callable[[str], Awaitable[None]],
) -> None:
    """Explore directions, submit proposals for experiment, and read the resulting feedback.

    START --> route_exploration_stage
                +--[initialize_explorer] --> create_workgroup (explorer + checker)
                |                            --> study_framework
                |                            --> fork_explorer [quota = 4]
                |                                 +--[explorer_i]
                |                                        --> route_exploration_stage[select_direction]
                +--[select_direction] ------> wait_direction_quota
                |                            --> exploration_direction (MCP)
                |                            --> wait_for_settle_and_tool_subflow[A=checking_direction,B=exploration_direction,C=retire]
                +--[checking_direction] ----> check_exploration_direction (MCP)
                |                            --> wait_for_settle_and_tool_subflow[A=direction_check_result,B=check_exploration_direction,C=retire]
                +--[exploration] ----------> [check_exploration_switch]
                |                                 --> exploration (MCP, including update_direction_pool)
                |                                 --> wait_for_settle_and_tool_subflow[A=checking,B=exploration,C=retire]
                +--[checking] --------------> check_exploration (MCP)
                |                            --> wait_for_settle_and_tool_subflow[A=route_exploration_stage[exploration/submit_to_experiment/retire],B=check_exploration,C=retire]
                +--[switch_exploration] ---> [check_exploration_switch]
                                              +--[preempt]
                                              |      --> wait_for_preempt
                                              |      --> route_exploration_stage[exploration]
                                              +--[create_explorer]
                                              |      --> create_workgroup
                                              |      --> fork_explorer
                                              |      --> route_exploration_stage[select_direction]
                                              +--[wake_explorer]
                                              |      --> wake_explorer
                                              +--[release_explorer_slot]
                                                     --> release_explorer_slot
                                                     --> route_exploration_stage[wake_explorer/create_explorer]
                +--[submit_to_experiment] --> update_direction_pool
                                              --> update_code_pool --> submit_to_experiment

    direction_check_result
        +--[direction_confirmed] --> update_direction_pool --> route_exploration_stage[exploration]
        +--[direction_rejected]  --> exploration_direction
        +--[exceed_limit_try]    --> retire

    retire --> retire_workgroup --> END
    """
    members = []
    roles = task_revision.task_submission.agent_team.roles
    for agent_class in (ExplorerAgent, CheckerAgent):
        config = workflow.default_agent_config
        if allocations := roles.get(agent_class.role_name):
            allocation = allocations[0]
            config = replace(config, model=allocation.model, effort=allocation.effort)
        members.append((agent_class, config))

    await workflow.create_workgroup(workspace_id=workspace_id, agents=members)
    raise NotImplementedError("The exploration stages after workgroup creation are not implemented.")
