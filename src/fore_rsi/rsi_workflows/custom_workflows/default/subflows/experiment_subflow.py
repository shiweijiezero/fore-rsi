# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Experiment execution and result delivery for the default workflow."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


async def run_experiment_subflow(workflow: "DefaultWorkflow", workspace_id: str) -> None:
    """Record each experiment's command and result on the corresponding exploration entry.

    START --> route_experiment_stage
                +--[initialize_experimenter] --> create_experimenter_workgroup
                |                                --> study_experiment
                |                                --> fork_experimenter [seed = study_experiment, quota = 2]
                |                                     +--[experimenter_1] --> route_experiment_stage[select_resources]
                |                                     +--[experimenter_2] --> route_experiment_stage[select_resources]
                +--[select_resources] ------> lock_select_resources
                |                            --> select_experimenter_resources
                |                            --> wait_for_settle --> tool_submission_status
                |                                +--[submitted] -------> unlock_select_resources
                |                                +--[not_submitted] ---> select_experimenter_resources
                |                                +--[exceed_limit_try] -> abort_resource_selection
                +--[experiment] ------------> select_experimenter (blocking with quota) --> experiment (running)
                                             --> wait_for_settle --> tool_submission_status
                                                 +--[submitted] -------> publish_result
                                                 +--[not_submitted] ---> experiment
                                                 +--[exceed_limit_try] -> exit_node

    unlock_select_resources --> END
    abort_resource_selection (release the selection lock without an assignment) --> exit_node
    exit_node --> END
    publish_result --> exploration_pool
    """
    raise NotImplementedError("The experiment subflow is not implemented.")
