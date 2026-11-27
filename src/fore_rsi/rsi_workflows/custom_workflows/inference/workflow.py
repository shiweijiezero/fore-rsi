# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Inference optimization workflow assembled from domain-specific subflows."""

from functools import partial
from pathlib import Path
from typing import cast

from langgraph.graph import END, START, StateGraph

from fore_rsi.config import AgentConfig, WorkflowConfig
from fore_rsi.rsi_workflows.base_agent import BaseAgent
from fore_rsi.rsi_workflows.custom_workflows.default.agents.coordinator import (
    CoordinatorAgent,
)
from fore_rsi.rsi_workflows.custom_workflows.default.agents.worker import WorkerAgent
from fore_rsi.rsi_workflows.custom_workflows.default.subflows.general import (
    wait_for_task_submission,
)
from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.experiment_subflow import (
    build_experiment_subflow,
)
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.exploration_subflow import (
    build_exploration_subflow,
)
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.initial_explorer_subflow import (
    build_initial_explorer_subflow,
)
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.initial_experimenter_subflow import (
    build_initial_experimenter_subflow,
)
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.watchdog_subflow import (
    build_watchdog_subflow,
)
from fore_rsi.rsi_workflows.custom_workflows.inference.subflows.work_subflow import (
    build_work_subflow,
)


class InferenceWorkflow(DefaultWorkflow):
    """Run the detailed Explorer, Worker, and Experimenter loop for inference optimization."""

    workflow_name = "inference"
    agent_roles = {**DefaultWorkflow.agent_roles, "Worker": WorkerAgent}

    async def request_agent_creation(
        self,
        state: dict[str, object],
        *,
        agent_class: type[BaseAgent],
        agent_config: AgentConfig,
        workgroup_name: str | None = None,
    ) -> dict[str, object]:
        """Schedule a member and pass its identity to the next inference graph node."""
        agent = await self.agent_scheduler.create_agent(
            agent_class=agent_class,
            agent_name=cast(str, state.get("agent_name") or self.next_agent_name(agent_class.role_name)),
            workgroup_name=workgroup_name or cast(str | None, state.get("workgroup_name")),
            agent_config=agent_config,
            workflow=self,
            workspace_id=cast(str, state["workspace_id"]),
            is_entry_agent=bool(state.get("is_entry", False)),
        )
        return {**state, "agent": agent, "agent_name": agent.agent_name, "workgroup_name": agent.workgroup.workgroup_name}

    async def parse_task(self, state: dict[str, object]) -> None:
        """Dispatch the inference graph's file-parsing step to its Coordinator."""
        coordinator = cast(CoordinatorAgent, state["agent"])
        await coordinator.parse_task(cast(Path, self.config.task))

    def build_workflow_nodes(self, graph: StateGraph) -> None:
        """Add inference task intake, initialization, and area nodes."""
        coordinator_node_name = f"create_{CoordinatorAgent.role_name.lower()}"
        graph.add_node(
            coordinator_node_name,
            partial(
                self.request_agent_creation,
                agent_class=CoordinatorAgent,
                agent_config=self.default_agent_config,
                workgroup_name=WorkflowConfig.GLOBAL_WORKGROUP_NAME,
            ),
        )
        graph.add_node(
            "wait_for_task_submission",
            partial(wait_for_task_submission, self),
        )
        graph.add_node("initialize_first_task", partial(wait_for_task_submission, self))
        graph.add_node(
            "initialize_explorer_context",
            build_initial_explorer_subflow(self).compile(),
        )
        graph.add_node(
            "initialize_experimenter_pool",
            build_initial_experimenter_subflow(self).compile(),
        )
        graph.add_node("update_task_context", lambda workflow_state: {})
        graph.add_node("route_workflow_stage", lambda workflow_state: {})
        graph.add_node(
            "run_exploration_area",
            build_exploration_subflow(self).compile(),
        )
        graph.add_node("run_work_area", build_work_subflow(self).compile())
        graph.add_node(
            "run_experiment_area",
            build_experiment_subflow(self).compile(),
        )
        graph.add_node(
            "run_watchdog_area",
            build_watchdog_subflow(self).compile(),
        )
        graph.add_node("parse_task", self.parse_task)

    def build_workflow_edges(self, graph: StateGraph) -> None:
        """Add inference task intake, initialization, area routing, and finish edges."""
        #
        # START -> create_coordinator
        #              +--[have_task]--------> parse_task -> initialize_first_task
        #              +--[await_user_input]---------------> initialize_first_task
        #
        # submit_task has already published the revision and applied its quotas.
        #                    initialize_first_task  wait_for_task_submission -> update_task_context
        #                         +---------+                 |
        #                         |         |                 v
        #                         v         v        route_workflow_stage
        #              initialize_explorer_context  initialize_experimenter_pool
        #                         |                 +--> END
        #                         v
        #              run_exploration_area                 route_workflow_stage
        #                         |                          +--> run_exploration_area
        #                         +--------------------------+--> run_work_area
        #                                                    +--> run_experiment_area
        #                                                    +--> run_watchdog_area
        #                                                    +--> wait_for_task_submission / END
        coordinator_node_name = f"create_{CoordinatorAgent.role_name.lower()}"
        graph.add_edge(START, coordinator_node_name)
        graph.add_conditional_edges(
            coordinator_node_name,
            lambda workflow_state: "have_task"
            if self.config.task is not None
            else "await_user_input",
            {
                "have_task": "parse_task",
                "await_user_input": "initialize_first_task",
            },
        )
        graph.add_edge("parse_task", "initialize_first_task")
        graph.add_edge("wait_for_task_submission", "update_task_context")
        graph.add_edge("initialize_first_task", "initialize_explorer_context")
        graph.add_edge("initialize_first_task", "initialize_experimenter_pool")
        graph.add_edge("initialize_explorer_context", "run_exploration_area")
        graph.add_edge("initialize_experimenter_pool", END)
        graph.add_edge("update_task_context", "wait_for_task_submission")
        graph.add_conditional_edges(
            "route_workflow_stage",
            lambda workflow_state: workflow_state.get(
                "next_workflow_stage", "wait_for_task_submission"
            ),
            {
                "exploration": "run_exploration_area",
                "work": "run_work_area",
                "experiment": "run_experiment_area",
                "watchdog": "run_watchdog_area",
                "wait_for_task_submission": "wait_for_task_submission",
                "finish": END,
            },
        )
        graph.add_edge("run_exploration_area", "route_workflow_stage")
        graph.add_edge("run_work_area", "route_workflow_stage")
        graph.add_edge("run_experiment_area", "route_workflow_stage")
        graph.add_edge("run_watchdog_area", "route_workflow_stage")
