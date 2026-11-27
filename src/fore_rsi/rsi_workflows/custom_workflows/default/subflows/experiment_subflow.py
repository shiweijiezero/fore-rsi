# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Experiment execution and result delivery for the default workflow."""

from typing import TYPE_CHECKING

from fore_rsi.rsi_workflows.workflow_runtimes.task import TaskRevision

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


async def run_experiment_subflow(
    workflow: "DefaultWorkflow",
    workspace_id: str,
    task_revision: TaskRevision,
) -> None:
    """Run the submitted proposals and send each experiment result back to exploration.

    START --> route_experiment_stage
                +--[initialize_experimenter] --> create_experimenter_workgroup
                |                                --> study_experiment
                |                                --> fork_experimenter [seed = study_experiment, quota = 2]
                |                                     +--[experimenter_1] --> route_experiment_stage[select_resources]
                |                                     +--[experimenter_2] --> route_experiment_stage[select_resources]
                +--[select_resources] ------> lock_select_resources
                |                            --> select_experimenter_resources
                |                            --> wait_for_settle_and_tool_subflow[A=unlock_select_resources,B=select_experimenter_resources,C=abort_resource_selection]
                +--[experiment] ------------> select_experimenter (blocking with quota) --> experiment (running)
                                             --> wait_for_settle_and_tool_subflow[A=publish_result,B=experiment,C=exit_node]

    unlock_select_resources --> END
    abort_resource_selection (release the selection lock without an assignment) --> exit_node
    exit_node --> END
    publish_result --> publish_experiment_result
    """
    try:
        raise NotImplementedError("The experiment subflow is not implemented.")
    finally:
        workflow.experiment_results.shutdown()
