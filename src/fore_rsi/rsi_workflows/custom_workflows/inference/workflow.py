# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Inference optimization entry point for the shared team workflow."""

from fore_rsi.rsi_workflows.custom_workflows.default.workflow import DefaultWorkflow


class InferenceWorkflow(DefaultWorkflow):
    """Run inference tasks with the default exploration and experiment subflows."""

    workflow_name = "inference"
