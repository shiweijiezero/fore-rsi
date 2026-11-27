# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Agent role quotas, creation admission, execution queues, and active slots."""

import asyncio
from collections import Counter, deque
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, NonNegativeInt

from fore_rsi.config import AgentConfig, ReasoningEffort
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent
from fore_rsi.rsi_workflows.types import RequiredText

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow
    from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup


class AgentAllocation(BaseModel):
    """One role's model, reasoning level and active slot allocation."""

    model: RequiredText
    effort: ReasoningEffort
    quota: NonNegativeInt | Literal["unlimited"]


class SchedulingPriority(IntEnum):
    """Rank queued Agent creation requests, with lower values taking precedence."""

    HIGH = 0
    MEDIUM = 1
    LOW = 2


@dataclass(eq=False)
class AgentCreationRequest:
    """One queue entry, distinct from other requests for the same quota and priority."""

    priority: SchedulingPriority
    quota_key: tuple[type[BaseAgent], str | None, str | None]


class AgentScheduler:
    """Own role quotas, Agent creation admission, queues, and active slots."""

    def __init__(
        self,
        role_classes: Mapping[str, type[BaseAgent]] | None = None,
    ) -> None:
        """Initialize role mappings, quota limits, queues, and active Agents."""
        self.role_classes = dict(role_classes or {})
        self.agent_name_counters: Counter[str] = Counter()
        # Every registered role starts with one slot for the native default model and effort.
        self.quotas: dict[
            tuple[type[BaseAgent], str | None, str | None],
            int | Literal["unlimited"],
        ] = {
            (agent_class, None, None): 1
            for agent_class in self.role_classes.values()
        }
        # Requests wait here until their role/model/effort quota admits creation.
        self.priority_queues: dict[SchedulingPriority, deque[AgentCreationRequest]] = {
            priority: deque() for priority in SchedulingPriority
        }
        self.active_agents: dict[
            BaseAgent,
            tuple[type[BaseAgent], str | None, str | None],
        ] = {}
        self.scheduler_condition = asyncio.Condition()

    @asynccontextmanager
    async def role_quota_update(
        self,
        role_allocations: Mapping[str, Sequence[AgentAllocation]],
    ) -> AsyncIterator[None]:
        """Validate allocations before publication and install them only if publication succeeds."""
        for role_name in role_allocations:
            if role_name not in self.role_classes:
                raise ValueError(
                    f"Unknown agent role {role_name!r}. "
                    f"Available roles: {', '.join(sorted(self.role_classes))}."
                )

        scheduler_quotas = {
            (
                self.role_classes[role_name],
                agent_allocation.model,
                agent_allocation.effort,
            ): agent_allocation.quota
            for role_name, agent_allocations in role_allocations.items()
            for agent_allocation in agent_allocations
        }
        for quota_limit in scheduler_quotas.values():
            if quota_limit != "unlimited" and (
                type(quota_limit) is not int or quota_limit < 0
            ):
                raise ValueError('Agent quota must be a nonnegative integer or "unlimited".')

        async with self.scheduler_condition:
            yield
            # Explicit task allocations override defaults; omitted combinations return to one slot.
            self.quotas.update(scheduler_quotas)
            for quota_key in tuple(self.quotas):
                if quota_key not in scheduler_quotas:
                    self.quotas[quota_key] = 1
            self.scheduler_condition.notify_all()

    async def create_agent[AgentT: BaseAgent](
        self,
        *,
        agent_class: type[AgentT],
        workgroup: "Workgroup",
        agent_config: AgentConfig,
        workflow: "BaseWorkflow",
        workspace_id: str,
        is_entry_agent: bool,
        priority: SchedulingPriority = SchedulingPriority.LOW,
    ) -> AgentT:
        """Wait for quota and return a ready agent in the supplied workgroup."""
        quota_key = (agent_class, agent_config.model, agent_config.effort)
        creation_request = AgentCreationRequest(priority=priority, quota_key=quota_key)

        try:
            # Admission happens before Agent construction and Native runtime creation.
            async with self.scheduler_condition:
                # The entry agent can select a model and effort before the first task supplies quotas.
                if is_entry_agent and quota_key not in self.quotas:
                    self.quotas[quota_key] = self.quotas[(agent_class, None, None)]
                self.priority_queues[priority].append(creation_request)
                self.scheduler_condition.notify_all()
                # wait_for rechecks the predicate after each quota or queue change.
                await self.scheduler_condition.wait_for(
                    lambda: self.find_next_eligible_creation_request()
                    is creation_request
                )
                self.priority_queues[priority].remove(creation_request)
                role_prefix = agent_class.role_name.lower()
                self.agent_name_counters[role_prefix] += 1
                agent_name = f"{role_prefix}-{self.agent_name_counters[role_prefix]}"
                agent = agent_class(agent_name, workgroup, agent_config, workflow=workflow)
                workgroup.agents[agent_name] = agent
                self.active_agents[agent] = quota_key
        except BaseException:
            # A cancelled or rejected request must not block later requests in the same queue.
            await self.cancel_agent_creation(creation_request)
            raise

        try:
            await agent.agent_runtime.start(
                workspace_id,
                is_entry=is_entry_agent,
                system_prompt=agent.system_prompt,
            )
        except BaseException:
            self.active_agents.pop(agent, None)
            workgroup.agents.pop(agent_name, None)
            agent.state = AgentState.FAILED
            async with self.scheduler_condition:
                self.scheduler_condition.notify_all()
            raise

        return agent

    async def cancel_agent_creation(
        self, creation_request: AgentCreationRequest
    ) -> bool:
        """Remove a pending Agent creation request and wake other waiters."""
        async with self.scheduler_condition:
            queued_agents = self.priority_queues[creation_request.priority]
            if creation_request not in queued_agents:
                return False
            queued_agents.remove(creation_request)
            self.scheduler_condition.notify_all()
            return True

    def find_next_eligible_creation_request(self) -> AgentCreationRequest | None:
        """Return the first queued request whose quota currently has capacity."""
        return next(
            (
                creation_request
                for priority in SchedulingPriority
                for creation_request in self.priority_queues[priority]
                if self.has_capacity(creation_request.quota_key)
            ),
            None,
        )

    async def release(self, agent: BaseAgent) -> bool:
        """Release an active Agent's execution slot."""
        async with self.scheduler_condition:
            # Releasing a slot wakes the next eligible creation request.
            if agent not in self.active_agents:
                return False
            del self.active_agents[agent]
            self.scheduler_condition.notify_all()
            return True

    def has_capacity(
        self,
        quota_key: tuple[type[BaseAgent], str | None, str | None],
    ) -> bool:
        """Return whether a quota key permits another active Agent."""
        quota_limit = self.quotas[quota_key]
        if quota_limit == "unlimited":
            return True
        active_count = sum(
            active_quota_key == quota_key
            for active_quota_key in self.active_agents.values()
        )
        return active_count < quota_limit
