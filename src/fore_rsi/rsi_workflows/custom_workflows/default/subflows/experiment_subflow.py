# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Keep the experiment team ready to measure approved exploration items and return their reports."""

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from fore_rsi.rsi_workflows.base_agent import AgentState

from ..agents.experimenter import ExperimenterAgent

if TYPE_CHECKING:
    from fore_rsi.rsi_workflows.workflow_runtimes.task import (
        TaskRevision,
        TaskSubmission,
    )
    from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup

    from ..workflow import DefaultWorkflow


class ExperimentSubflow:
    """Own the resident Experimenters, their resource allocations and the measurement queue."""

    def __init__(self, workflow: "DefaultWorkflow", workspace_id: str) -> None:
        """Bind this session's pool; team preparation starts with the first task declaration."""
        self.workflow = workflow
        self.workspace_id = workspace_id
        self.exploration_pool = workflow.exploration_pool
        self.dispatch_requested = asyncio.Event()
        self.pending_team_revision: TaskRevision | None = None
        self.coordination_blocker: str | None = None
        self.seed_experimenter: ExperimenterAgent | None = None
        self.starting_group: asyncio.Task[Workgroup] | None = None
        self.resource_units: dict[str, str] = {}
        # None until the member participates; an empty allocation is an explicit standby choice.
        self.member_resources: dict[ExperimenterAgent, tuple[str, ...] | None] = {}
        self.initial_selection: TaskRevision | None = None
        self.replying_members: set[ExperimenterAgent] = set()

        # Each item has one experiment. Keep its completion signal with its execution owner until publication.
        self.team_experiments: dict[str, asyncio.Future[None]] = {}  # In submission order.
        self.external_experiments: dict[str, asyncio.Future[None]] = {}
        self.assigned_experiments: dict[str, ExperimenterAgent] = {}  # Held through verified cleanup.

    async def run(self) -> None:
        """Prepare the team before taking work. A team change stops admission, not running measurements.

        [start experiment subflow] --> study framework once --> retain seed --> fork configured team
        [initial resource selection] --> each member waits for work as soon as its own choice settles
        [idle member with resources] --> measure oldest queued item --> report and clean up --> wait for work
        [team or budget changed] --> pause claims --> drain runs and cleanup --> resize --> all choose --> resume

        Explorer submissions stay in the queue throughout a team change. Shutdown closes the resident sessions.
        """
        preparation = None
        async with asyncio.TaskGroup() as tasks:
            while True:
                self.dispatch_requested.clear()
                revision = self.pending_team_revision
                if (revision is not None and (preparation is None or preparation.done())
                        and not self.assigned_experiments and not self.replying_members):
                    preparation = tasks.create_task(self.prepare_experiment_team(revision))
                    preparation.add_done_callback(lambda _: self.dispatch_requested.set())
                # In-flight measurements can still need an answer from an idle teammate while
                # the team drains. A resize stops new measurement claims, not that conversation.
                if self.can_start_measurements or self.assigned_experiments:
                    self.dispatch_to_idle_experimenters(tasks)
                await self.dispatch_requested.wait()

    @property
    def can_start_measurements(self) -> bool:
        """First-time selections go live individually; later reallocations take effect together."""
        revision = self.pending_team_revision
        return (not self.external_experiments and not self.coordination_blocker
                and (revision is None or revision is self.initial_selection))

    async def prepare_experiment_team(self, revision: "TaskRevision") -> None:
        """Bring the team to its requested size and let members divide the task's resource budget."""
        self.resource_units = revision.task_submission.constraints.resources.experiment_resources.units or {
            "shared": "Use the task's undivided measurement budget exclusively within its stated limits."
        }
        enabled = revision.task_submission.agent_team.roles.get(ExperimenterAgent.role_name)
        quota = self.workflow.agent_scheduler.max_concurrent_workgroups((ExperimenterAgent,)) if enabled else 0
        team_size = len(self.resource_units) if quota == "unlimited" else quota
        if team_size and self.seed_experimenter is None:
            seed = await self.start_experimenter(fork_source=None)
            if seed is None:
                return
            await seed.study_framework(revision.revision_file_path.resolve())
            await seed.retain_as_fork_source()
            self.seed_experimenter = seed
            self.initial_selection = revision

        await self.resize_team(revision, team_size)
        if self.pending_team_revision is not revision:
            return
        blocker = await self.coordinate_resources(revision)
        self.initial_selection = None
        if self.pending_team_revision is revision:
            self.pending_team_revision = None
            self.coordination_blocker = blocker
            if blocker:
                notice = f"Experiments remain queued: {blocker} Resubmit the task to retry resource coordination."
                logger.warning("{}", notice)
                for member in self.workflow.workgroups.global_workgroup.agents.values():
                    member.add_to_inbox(notice)

    async def resize_team(self, revision: "TaskRevision", team_size: int) -> None:
        """Retire only surplus or ineligible members; fork additions without restarting the surviving sessions."""
        while self.pending_team_revision is revision:
            groups = [member.workgroup for member in self.member_resources]
            retiring = self.workflow.agent_scheduler.select_workgroup_to_retire(groups, capacity=team_size)
            if retiring is None:
                break
            member = retiring.member(ExperimenterAgent)
            await retiring.close_members()
            del self.member_resources[member]

        while len(self.member_resources) < team_size and self.pending_team_revision is revision:
            member = await self.start_experimenter(fork_source=self.seed_experimenter)
            if member is None:
                return
            self.member_resources[member] = None

    async def coordinate_resources(self, revision: "TaskRevision") -> str | None:
        """Let each member claim a share of the same inventory, seeing all prior choices."""
        for member in self.member_resources:
            self.member_resources[member] = None
        for member in self.member_resources:
            blocker = await member.choose_resources(revision)
            if self.pending_team_revision is not revision:
                return None
            if blocker:
                if self.initial_selection is not revision:
                    return f"{member.get_full_name()}: {blocker}"
                # No work has been issued to this member. Its failure must not strand earlier startup grants.
                self.member_resources[member] = None
                logger.warning("{} could not select measurement resources: {}", member.get_full_name(), blocker)
            self.dispatch_requested.set()  # At startup this member can take work during the next selection.
        if self.member_resources and not any(self.member_resources.values()):
            return "No Experimenter claimed measurement resources."
        return None

    def resource_assignments(self) -> dict[str, tuple[str, ...] | None]:
        """Show each Experimenter's current share under its address in the team directory."""
        return {member.get_full_name(): units for member, units in self.member_resources.items()}

    def set_member_resources(self, member: ExperimenterAgent, resource_ids: list[str], reason: str) -> dict[str, object]:
        """Apply a member's complete allocation without yielding between checking and claiming units."""
        if member not in self.member_resources or member.state in (AgentState.RETIRED, AgentState.FAILED):
            raise ValueError("Only resident Experimenters may claim measurement resources.")
        if member.choosing_for is not None:
            member.require_tool_submission("set_experiment_resources")
            if self.pending_team_revision is not member.choosing_for:
                raise ValueError("The team allocation changed. Wait for the revised selection turn.")
        else:
            if not self.can_start_measurements:
                raise ValueError("Resource changes are paused until the team finishes reallocating.")
            if member not in self.replying_members:
                member.require_tool_submission("submit_experiment_report")
                if member not in self.assigned_experiments.values() or member.step_tool_calls.attempt_number != 1:
                    raise ValueError("Change resources during measurement or an assigned coordination turn.")

        requested = tuple(dict.fromkeys(resource_ids))
        for unit in requested:
            if unit not in self.resource_units:
                raise ValueError(f"Unknown resource {unit!r}. Choose from {', '.join(self.resource_units)}.")
            for owner, held in self.member_resources.items():
                if owner is not member and held and unit in held:
                    raise ValueError(f"{unit} belongs to {owner.get_full_name()}. Coordinate its release first.")
        self.member_resources[member] = requested
        notice = f"{member.get_full_name()} now holds {', '.join(requested) or 'no units (standby)'}. {reason}"
        for teammate in self.member_resources:
            if teammate is not member:
                teammate.add_to_inbox(notice)
        for item_id, owner in self.assigned_experiments.items():
            if owner is member:
                self.exploration_pool.append_record(item_id, notice)
        self.dispatch_requested.set()
        return {"your_resources": list(requested), "team_allocations": self.resource_assignments()}

    def queue_exploration_item_for_experiment(self, exploration_item_id: str) -> asyncio.Future[None]:
        """Queue one measurement of the approved exploration item and return its completion signal."""
        exploration_item = self.exploration_pool.get(exploration_item_id)
        if exploration_item.experiment_result is not None:
            raise ValueError(f"Exploration item {exploration_item_id} already has a report. Submit a child item for new work.")
        if (exploration_item.status != "exploring" or not exploration_item.code_workspace_path
                or not exploration_item.experiment_commands):
            raise ValueError(f"Exploration item {exploration_item_id} has no runnable experiment.")
        revision = self.workflow.task.current_task
        assert revision is not None
        team_measures = bool(revision.task_submission.agent_team.roles.get(ExperimenterAgent.role_name))
        owner = "Experimenter queue" if team_measures else "External operator"
        commands = "\n".join(exploration_item.experiment_commands)
        self.exploration_pool.append_record(exploration_item_id, (
            f"\n## Experiment\n\nAssigned to: {owner}\n\n"
            f"Working directory: `{exploration_item.code_workspace_path}`\n\n```sh\n{commands}\n```\n"
        ))
        self.exploration_pool.update(exploration_item_id, status="queued_for_experiment")
        completion = asyncio.get_running_loop().create_future()
        queue = self.team_experiments if team_measures else self.external_experiments
        queue[exploration_item_id] = completion
        self.dispatch_requested.set()
        return completion

    def dispatch_to_idle_experimenters(self, tasks: asyncio.TaskGroup) -> None:
        """Give idle members a requested conversation turn or the oldest available measurement."""
        busy = set(self.assigned_experiments.values()) | self.replying_members
        waiting = iter([item_id for item_id in self.team_experiments if item_id not in self.assigned_experiments])
        for member, resources in self.member_resources.items():
            if member in busy or member.choosing_for is not None or resources is None or member.state == AgentState.FAILED:
                continue
            if member.has_reply_request:
                self.replying_members.add(member)
                tasks.create_task(self.handle_team_question(member))
            elif self.can_start_measurements and resources and (exploration_item_id := next(waiting, None)) is not None:
                self.assigned_experiments[exploration_item_id] = member
                tasks.create_task(self.measure_exploration_item(member, exploration_item_id))

    async def handle_team_question(self, member: ExperimenterAgent) -> None:
        """Run a requested reply between measurements, never concurrently with the member's native turn."""
        try:
            if member.has_reply_request and (self.can_start_measurements or self.assigned_experiments):
                await member.reply_to_teammates()
        finally:
            self.replying_members.remove(member)
            if member.state == AgentState.FAILED and self.pending_team_revision is None:
                self.pending_team_revision = self.workflow.task.current_task
            self.dispatch_requested.set()

    async def measure_exploration_item(self, member: ExperimenterAgent, exploration_item_id: str) -> None:
        """Issue the approved commands with this member's resources and publish or hold the resulting report."""
        if not self.can_start_measurements:
            del self.assigned_experiments[exploration_item_id]
            self.dispatch_requested.set()
            return
        resources = self.member_resources[member]
        assert resources
        grant = f"{member.get_full_name()} holds {', '.join(resources)} for item {exploration_item_id}."
        self.exploration_pool.append_record(exploration_item_id, f"\n{grant}\n")
        self.exploration_pool.update(exploration_item_id, status="experimenting")
        outcome = None
        try:
            outcome = await member.run_experiment(exploration_item_id, grant)
        finally:
            report, experiment_summary, resources_released = outcome or member.unsettled_report("Measurement interrupted.")
            self.finish_measurement(exploration_item_id, report, experiment_summary, resources_released=resources_released)
            if member.state == AgentState.FAILED and self.pending_team_revision is None:
                self.pending_team_revision = self.workflow.task.current_task
            self.dispatch_requested.set()

    def finish_measurement(
        self, exploration_item_id: str, report: str, experiment_summary: str, *, resources_released: bool,
    ) -> None:
        """Publish evidence once the resources and checkout can be reused.

        [cleanup confirmed] --> publish result --> original group resumes
        [cleanup unknown] --> hold resources and checkout --> confirm_cleanup --> publish result
        """
        if resources_released:
            self.publish_result(exploration_item_id, report, experiment_summary)
            return

        # Keep the member and its resources assigned until the operator confirms cleanup.
        self.exploration_pool.update(exploration_item_id, experiment_result=report, experiment_summary=experiment_summary)
        self.exploration_pool.append_record(exploration_item_id, (
            "\nCleanup unconfirmed. Report verified cleanup to the Coordinator before reusing the assigned resources.\n"
        ))

    def confirm_cleanup(self, exploration_item_id: str, evidence: str) -> None:
        """Publish a held report once the operator confirms this item's measurement has stopped."""
        if exploration_item_id in self.assigned_experiments:
            item = self.exploration_pool.get(exploration_item_id)
            if item.experiment_result is not None:
                report = f"{item.experiment_result}\n\nCleanup confirmed: {evidence}"
                self.publish_result(exploration_item_id, report, item.experiment_summary)
                return
        raise ValueError(f"No resources are awaiting cleanup for exploration item {exploration_item_id}.")

    def record_external_result(self, exploration_item_id: str, report: str, experiment_summary: str) -> None:
        """Accept the operator's report only for an item assigned to external measurement."""
        if exploration_item_id not in self.external_experiments:
            raise ValueError(f"Exploration item {exploration_item_id} is not waiting for an external report.")
        self.publish_result(exploration_item_id, report, experiment_summary)

    def publish_result(self, exploration_item_id: str, report: str, experiment_summary: str | None) -> None:
        """Save the item's report and release its assignment before waking the original group."""
        self.exploration_pool.append_record(exploration_item_id, f"\n**Experiment result:**\n\n{report}\n")
        self.exploration_pool.update(
            exploration_item_id, experiment_result=report, experiment_summary=experiment_summary, status="exploring",
        )
        if exploration_item_id in self.external_experiments:
            completion = self.external_experiments.pop(exploration_item_id)
        else:
            del self.assigned_experiments[exploration_item_id]
            completion = self.team_experiments.pop(exploration_item_id)
        completion.set_result(None)
        self.dispatch_requested.set()

    def request_team_update(self, previous: "TaskRevision | None", revision: "TaskRevision") -> None:
        """Stop claims on a team change; resubmitting after a coordination blocker retries the allocation."""
        task = revision.task_submission
        incomplete_startup = self.pending_team_revision is None and None in self.member_resources.values()
        if previous is not None and self.coordination_blocker is None and not incomplete_startup:
            old = previous.task_submission
            if (task.agent_team.roles.get(ExperimenterAgent.role_name) == old.agent_team.roles.get(ExperimenterAgent.role_name)
                    and task.constraints.resources == old.constraints.resources):
                return
        self.pending_team_revision = revision
        self.coordination_blocker = None
        # A launch can be waiting for a slot the new quota no longer grants. Native turns already
        # studying, coordinating or measuring are allowed to settle; only pending creation is cancelled.
        if self.starting_group is not None:
            self.starting_group.cancel()
            self.starting_group = None
        self.dispatch_requested.set()

    def validate_execution_mode(self, submission: "TaskSubmission") -> None:
        """Do not hand the budget to an external operator while the team's measurements are outstanding."""
        team_measures = submission.agent_team.roles.get(ExperimenterAgent.role_name)
        if not team_measures and self.team_experiments:
            raise ValueError("Finish the team measurements before switching to external execution. "
                             "Set the Experimenter quota to zero to pause new starts.")

    async def start_experimenter(self, *, fork_source: ExperimenterAgent | None) -> ExperimenterAgent | None:
        """Start one member under scheduler admission; a superseding team request may withdraw the launch."""
        try:
            async with asyncio.TaskGroup() as startup:
                launch = self.starting_group = startup.create_task(self.workflow.workgroups.create(
                    workspace_id=self.workspace_id, agents=(ExperimenterAgent,), fork_source=fork_source,
                    is_fork_seed=fork_source is None,
                ))
        finally:
            self.starting_group = None
        return None if launch.cancelled() else launch.result().member(ExperimenterAgent)
