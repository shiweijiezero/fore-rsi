# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Accept an Experimenter's resource allocation and its observed run report."""

from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from fore_rsi.rsi_workflows.types import RequiredText, SingleLineText

if TYPE_CHECKING:
    from .agent import ExperimenterAgent


async def set_experiment_resources(
    resource_ids: list[RequiredText], reason: RequiredText, *, experimenter: "ExperimenterAgent",
) -> dict[str, object]:
    """Declare the full set of task resources you will use. An empty list means standby.

    Keep any units still in use. Omit a unit only after checking that your jobs no longer use it.
    Coordinate changes with teammates by message. Only this tool's successful result changes your
    allocation: you can claim free units, never units another member still holds.
    """
    try:
        return experimenter.workflow.experiments.set_member_resources(experimenter, resource_ids, reason)
    except ValueError as error:
        raise ToolError(str(error)) from error


async def submit_experiment_report(
    report: RequiredText, experiment_summary: SingleLineText, resources_released: bool, *, experimenter: "ExperimenterAgent",
) -> dict[str, bool]:
    """Submit the detailed report, a short outcome label and the cleanup status of this run.

    Use one line for experiment_summary, e.g. 'throughput +20%', '3/3 passed' or 'no data'.
    In report, identify the measured source version, conditions, commands, observed values and paths to
    supporting logs or artifacts. Describe outstanding work by job or service identity. Set
    resources_released to true only when the allocation is safe for the next experiment, including
    when this run never used it. Use false if a job may still be running or cleanup is unconfirmed.
    """
    experimenter.require_tool_submission(submit_experiment_report.__name__)
    experimenter.report = report, experiment_summary, resources_released
    return {"submitted": True}
