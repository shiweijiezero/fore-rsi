# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Tools for the default workflow's Explorer."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fore_rsi.rsi_workflows.types import RequiredText

#复用
# class ExplorationSubmission(BaseModel):
#     """The artifacts and findings submitted by an Explorer for review."""

#     model_config = ConfigDict(extra="forbid", strict=True)

#     findings: RequiredText  #探索发现、完成了什么
#     artifacts: list[ExplorationArtifact] = Field(min_length=1)  
#     evidence: list[RequiredText] = Field(default_factory=list)      #	验证结果、实验记录等，可以为空


@dataclass(frozen=True)
class ExplorationResult:
    """A submission associated with its direction, task revision, and author."""    
    submission: ExplorationSubmission


async def submit_exploration(
    submission: ExplorationSubmission,
    *,
    record_submission: Callable[[str, ExplorationSubmission], None],
) -> dict[str, object]:
    """Submit work from the current exploration round for Checker review.

    When the work is ready for review, summarize what you found, provide at
    least one artifact the Checker can locate, and explain what the Checker
    should assess. Cite the sources you examined and describe any gaps in
    the available evidence.

    For a code change, explain what changed and how you verified it. In an
    experiment proposal, describe the hypothesis, the comparison, and the
    measurements you plan to collect.

    After a successful exploration round, the workflow records the submission
    under the corresponding task revision and exploration direction.
    """
    
    #record_submission(submission)
    return {"exploration_submitted": True}
