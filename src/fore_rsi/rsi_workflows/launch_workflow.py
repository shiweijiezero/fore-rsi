# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Load a workflow by its registered CLI name and construct its runner."""

from pkgutil import resolve_name

from fore_rsi.config import Config
from fore_rsi.rsi_workflows.workflow_runtimes.workflow_runner import WorkflowRunner

# Store import paths rather than classes so each workflow loads only its own dependencies.
WORKFLOW_ENTRY_POINTS = {
    "default": "fore_rsi.rsi_workflows.custom_workflows.default.workflow:DefaultWorkflow",
    "inference": "fore_rsi.rsi_workflows.custom_workflows.inference.workflow:InferenceWorkflow",
}


def create_workflow_runner(config: Config) -> WorkflowRunner:
    """Return an unstarted runner for the workflow selected by the resolved application configuration."""
    workflow_name = config.workflow.workflow_name
    entry_point = WORKFLOW_ENTRY_POINTS.get(workflow_name)
    if entry_point is None:
        available = ", ".join(sorted(WORKFLOW_ENTRY_POINTS))
        raise ValueError(f"Unknown workflow {workflow_name!r}. Available workflows: {available}.")

    return WorkflowRunner(
        workflow_class=resolve_name(entry_point),
        workflow_config=config.workflow,
        session_name=config.session,
        cache_dir=config.cache_dir,
    )
