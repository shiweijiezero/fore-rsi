# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Explorer research, implementation, feedback, and Workgroup lifecycle subflow."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from langgraph.graph import StateGraph

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
    await workflow.create_workgroup(
        workspace_id=workspace_id,
        agents=[ExplorerAgent, CheckerAgent],
        task_revision=task_revision,
    )
    raise NotImplementedError("The exploration stages after workgroup creation are not implemented.")


def build_exploration_subflow(workflow: "DefaultWorkflow") -> StateGraph:
    """Build the Explorer subflow for direction selection, implementation, and handoff.

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
                                              --> update_code_pool --[Command.PARENT]--> route_workflow_stage[experiment]

    direction_check_result
        +--[direction_confirmed] --> update_direction_pool --> route_exploration_stage[exploration]
        +--[direction_rejected]  --> exploration_direction
        +--[exceed_limit_try]    --> retire

    retire --> retire_workgroup --> exit_node --> END
    """
    graph = StateGraph(dict)

    # Agent methods send prompts; the subflow owns routing.
    graph.add_node(
        "exploration",
        ExplorerAgent.exploration,
    )

    graph.add_node(
        "check_exploration",
        CheckerAgent.check_exploration,
    )

    return graph
