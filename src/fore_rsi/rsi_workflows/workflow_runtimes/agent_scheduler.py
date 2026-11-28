# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Agent role quotas, creation admission, execution queues, and active slots."""

import asyncio
from collections import Counter, deque
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from enum import IntEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, NonNegativeInt

from fore_rsi.config import AgentConfig, ReasoningEffort
from fore_rsi.rsi_workflows.base_agent import AgentState, BaseAgent
from fore_rsi.rsi_workflows.types import RequiredText

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.agent_runtimes.base_runtime import AgentRuntime
    from fore_rsi.rsi_workflows.base_workflow import BaseWorkflow
    from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup


type Quota = int | Literal["unlimited"]
type ModelSettings = tuple[str | None, ReasoningEffort | None]
type Slot = tuple[type[BaseAgent], ModelSettings]


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
    """A request for any allocation of a role, or for specific native launch settings."""

    role: type[BaseAgent]
    settings: ModelSettings | None


class AgentScheduler:
    """Schedule agent starts against the current task's role, model and effort allocations.

    Workflows use the configured limits to plan workgroups. The scheduler grants actual slots
    to queued requests and counts each agent from the start of its launch until release.
    """

    def __init__(
        self,
        role_classes: Mapping[str, type[BaseAgent]] | None = None,
    ) -> None:
        """Initialize role mappings, quota limits, queues, and active Agents."""
        self.role_classes = dict(role_classes or {})
        self.agent_name_counters: Counter[str] = Counter()
        # Every registered role starts with one slot for the native default model and effort.
        self.quotas: dict[type[BaseAgent], dict[ModelSettings, Quota]] = {
            role: {(None, None): 1} for role in self.role_classes.values()
        }
        # Subscribers capture this event before reading quotas, so an update cannot be missed.
        self.quota_changed = asyncio.Event()
        # Requests wait here until their role/model/effort quota admits creation.
        self.priority_queues: dict[SchedulingPriority, deque[AgentCreationRequest]] = {
            priority: deque() for priority in SchedulingPriority
        }
        self.active_agents: dict[BaseAgent, Slot] = {}
        self.scheduler_condition = asyncio.Condition()

    def max_concurrent_workgroups(self, roles: Sequence[type[BaseAgent]]) -> Quota:
        """Return the configured group limit, including slots already in use.

        Add the model allocations for each role and divide by the number of members of that
        role in one group. The smallest finite result limits the team; a role with an
        unlimited allocation does not constrain it.
        """
        limits = []
        for member_role, count in Counter(roles).items():
            total = 0
            for limit in self.quotas[member_role].values():
                if limit == "unlimited":
                    break
                total += limit
            else:
                limits.append(total // count)
        return min(limits) if limits else "unlimited"

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

        updated: dict[type[BaseAgent], dict[ModelSettings, Quota]] = {}
        for name, role in self.role_classes.items():
            updated[role] = {
                (allocation.model, allocation.effort): allocation.quota
                for allocation in role_allocations.get(name, ())
            } or {(None, None): 1}

        async with self.scheduler_condition:
            yield
            # Replace the declaration, not the reservations: running turns may finish on removed models.
            if self.quotas != updated:
                self.quota_changed.set()
                self.quota_changed = asyncio.Event()
                self.scheduler_condition.notify_all()
            self.quotas = updated

    async def create_agent[AgentT: BaseAgent](
        self,
        *,
        agent_class: type[AgentT],
        workgroup: "Workgroup",
        agent_config: AgentConfig | None = None,
        fork_source: "AgentRuntime | None" = None,
        workflow: "BaseWorkflow",
        workspace_id: str,
        is_entry_agent: bool,
        priority: SchedulingPriority = SchedulingPriority.LOW,
    ) -> AgentT:
        """Start an agent on an available role allocation, honoring explicit launch settings when supplied."""
        fixed = (agent_config.model, agent_config.effort) if agent_config is not None else None
        request = AgentCreationRequest(agent_class, fixed)
        queue = self.priority_queues[priority]
        async with self.scheduler_condition:
            # The entry agent's CLI selection precedes the first task declaration.
            if is_entry_agent and fixed is not None and fixed not in self.quotas[agent_class]:
                self.quotas[agent_class] = {fixed: self.quotas[agent_class][None, None]}

            # Choose the request and reserve its slot under the same lock. A waiting request
            # sees the latest allocations each time another agent exits or the task changes.
            queue.append(request)
            try:
                while (selected := self.select_next_agent_to_start()) is None or selected[0] is not request:
                    await self.scheduler_condition.wait()
                _, settings = selected
                model, effort = settings
                config = replace(agent_config or workflow.default_agent_config, model=model, effort=effort)
                role_prefix = agent_class.role_name.lower()
                self.agent_name_counters[role_prefix] += 1
                agent_name = f"{role_prefix}-{self.agent_name_counters[role_prefix]}"
                agent = agent_class(agent_name, workgroup, config, workflow=workflow)
                workgroup.agents[agent_name] = agent
                self.active_agents[agent] = (agent_class, settings)
            finally:
                queue.remove(request)
                self.scheduler_condition.notify_all()

        # Native startup holds the reservation, not the lock. If it fails or is cancelled,
        # remove the member and free the slot for another request.
        try:
            await agent.agent_runtime.start(
                workspace_id,
                is_entry=is_entry_agent,
                system_prompt=agent.system_prompt,
                fork_source=fork_source,
            )
        except BaseException:
            workgroup.agents.pop(agent_name, None)
            agent.state = AgentState.FAILED
            await self.release(agent)
            raise

        return agent

    def select_next_agent_to_start(self) -> tuple[AgentCreationRequest, ModelSettings] | None:
        """Select the next eligible agent request by priority, then arrival order, with its model and effort."""
        occupied = Counter(self.active_agents.values())
        for priority in SchedulingPriority:
            for request in self.priority_queues[priority]:
                for settings, limit in self.quotas[request.role].items():
                    if request.settings is not None and request.settings != settings:
                        continue
                    if limit == "unlimited" or occupied[request.role, settings] < limit:
                        return request, settings
        return None

    async def release(self, agent: BaseAgent) -> bool:
        """Release an active Agent's execution slot."""
        async with self.scheduler_condition:
            # Releasing a slot wakes the next eligible creation request.
            if agent not in self.active_agents:
                return False
            del self.active_agents[agent]
            self.scheduler_condition.notify_all()
            return True

    def can_reuse_workgroup(self, workgroup: "Workgroup") -> bool:
        """Return whether every member of an idle workgroup can keep its existing model reservation."""
        return self.select_workgroup_to_retire([workgroup]) is None

    def select_workgroup_to_retire(
        self, idle_groups: Sequence["Workgroup"], *, capacity: int | None = None,
    ) -> "Workgroup | None":
        """Choose an idle group to release, preferring lower-priority groups when equally useful.

        Releasing one Explorer/Checker pair can satisfy two allocation cuts. Count both before
        retiring either session; callers recheck the remaining reservations after each retirement.
        """
        occupied = Counter(self.active_agents.values())
        over_quota = {slot for slot, count in occupied.items()
                      if (limit := self.quotas[slot[0]].get(slot[1], 0)) != "unlimited" and count > limit}
        retiring = idle_groups[-1] if capacity is not None and len(idle_groups) > capacity else None
        most_released = 0
        for group in reversed(idle_groups):
            excess = 0
            for member in group.agents.values():
                if member.state == AgentState.FAILED:
                    return group
                slot = self.active_agents.get(member)
                if slot is None or slot in over_quota:
                    excess += 1
            if excess > most_released:
                retiring, most_released = group, excess
        return retiring
