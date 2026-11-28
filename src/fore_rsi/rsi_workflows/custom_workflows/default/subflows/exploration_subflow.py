# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Schedule exploration groups from direction review through implementation and experiment analysis."""

import asyncio
from collections import Counter, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fore_rsi.rsi_workflows.workflow_runtimes.agent_scheduler import Quota
from fore_rsi.rsi_workflows.workflow_runtimes.workgroup import Workgroup

from ..agents.checker import CheckerAgent
from ..agents.explorer import ExplorerAgent

if TYPE_CHECKING:
    from ..workflow import DefaultWorkflow


@dataclass(frozen=True)
class NewExplorationRound:
    """Direction selection awaiting a group slot, including the parent a continuation must build on."""

    suggested_direction: str | None = None
    required_parent_exploration_id: str | None = None


type RoundDecision = NewExplorationRound | Literal["finish", "retire_workgroup"]
type ExplorationStepResult = tuple[str, asyncio.Future[None]] | RoundDecision


class ExplorationSubflow:
    """Own the baseline seed, runnable groups and experiment handoffs for one workflow."""

    def __init__(self, workflow: "DefaultWorkflow", workspace_id: str) -> None:
        """Bind this session's dispatch queues without starting any members."""
        self.workflow = workflow
        self.workspace_id = workspace_id
        self.tasks = asyncio.TaskGroup()
        self.seed_explorer: ExplorerAgent
        self.direction_selection_lock = asyncio.Lock()

        # Each group resumes its own round. The pool holds the evidence; these queues hold only assignments.
        self.directions_to_select: dict[Workgroup, NewExplorationRound] = {}
        self.waiting_for_experiment: dict[asyncio.Future[None], tuple[Workgroup, str]] = {}
        self.exploration_items_ready_for_analysis: dict[Workgroup, str] = {}
        self.running_steps: dict[asyncio.Task[ExplorationStepResult], Workgroup] = {}
        self.finish_review_attempts: Counter[Workgroup] = Counter()

        self.requested_directions: deque[str] = deque()
        self.direction_requested = asyncio.Event()

    async def run(self) -> None:
        """Prepare the baseline and dispatch until all rounds and their experiments have ended.

        initialize_explorers --> [dispatch at current quota]
            +-- report ready --> original group analyzes the same item first
            +-- direction requested and slot free --> select_direction
            +-- no slot --> wait; active steps finish and surplus idle members release their slots

        [step finished, report returned, direction requested or quota changed] --> dispatch again
        [no queued work, running steps or outstanding experiments] --> END
        """
        await self.initialize_explorers()

        async with self.tasks:
            while self.has_work:
                quota_changed = self.workflow.agent_scheduler.quota_changed
                self.direction_requested.clear()
                available = await self.apply_current_quota()
                if available is not None and not quota_changed.is_set():
                    self.assign_work(available)
                    await self.wait_for_progress(quota_changed)

                await self.collect_finished_work()

    async def initialize_explorers(self) -> None:
        """Prepare the shared baseline before any group selects a direction.

        [team quota available] --> start seed Explorer --> study_framework --> prepare_baseline
        [baseline ready] --> retain idle seed and release its slot --> wait_for_team_quota --> fork_explorers
        [first assignment] --> start Explorer from seed history + fresh Checker --> select_direction
        """
        await self.wait_for_team_quota()
        seed_group = await self.workflow.workgroups.create(
            workspace_id=self.workspace_id, agents=(ExplorerAgent,), is_fork_seed=True,
        )
        seed = seed_group.member(ExplorerAgent)
        try:
            revision = self.workflow.task.current_task
            assert revision is not None  # The Coordinator submits the task before exploration starts.
            await seed.study_framework(revision.revision_file_path.resolve())
            await seed.prepare_baseline()
            await seed.retain_as_fork_source()
        except BaseException:
            await seed_group.close_members()
            raise

        # The seed remains in its own pane until workflow shutdown; only its forks take direction assignments.
        self.seed_explorer = seed
        quota = await self.wait_for_team_quota()
        initial_groups = max(1, len(self.requested_directions)) if quota == "unlimited" else quota
        await self.fork_explorers(initial_groups)

    async def run_exploration_steps(
        self, group: Workgroup, assignment: NewExplorationRound | str,
    ) -> ExplorationStepResult:
        """Select and implement one new item, or analyze the measured item identified by its ID.

        [wait for selection lock] --> [select_direction] --> submit pending item --> [check_direction]
            +-- approved --> release lock --> [explore_item] in parallel with other groups
            +-- rejected, attempts remain --> keep lock --> [select_direction] for a new item
            +-- attempts exhausted --> release lock --> retire group

        [explore_item] --> [review_exploration]
            +-- continue_exploration --> [explore_item] on the same item with feedback
            +-- approve_for_experiment --> queue exploration item --> wait for its report
            +-- retire_workgroup --> retire item and group

        [report on original item] --> [analyse_experiment_result: Explorer calls submit_next_action]
            +-- continue_exploration --> new round --> [select_direction] for a child of the measured item
            +-- start_new_round --> new round --> [select_direction] with freely chosen parents
            +-- finish --> [review_finish]

        [review_finish]
            +-- approved --> finish group
            +-- rejected, attempts remain --> [analyse_experiment_result] with feedback on the same report
            +-- rejected on last attempt --> retire item and group

        On handoff, return the item ID and completion signal to the dispatcher; the report stays on the item.
        A required submission that exhausts its attempts retires the group.
        """
        workflow = self.workflow
        if not group.agents:
            await group.start_members(workflow, workflow.exploration_roles, workspace_id=self.workspace_id)
        if isinstance(assignment, str):
            return await self.decide_next_step_after_experiment(group, exploration_item_id=assignment)

        explorer = group.member(ExplorerAgent)
        checker = group.member(CheckerAgent)
        if assignment.suggested_direction is not None:
            explorer.add_to_inbox(f"Consider this requested direction: {assignment.suggested_direction}")
        exploration_item_id = await self.select_direction(explorer, checker, assignment.required_parent_exploration_id)
        if exploration_item_id is None:
            return "retire_workgroup"

        # Implementation and Checker rework share this item until it is measured or retired.
        exploration_pool = workflow.exploration_pool
        exploration_pool.update(exploration_item_id, status="exploring")
        feedback = None
        while await explorer.explore_item(exploration_item_id, feedback):
            review = await checker.review_exploration(exploration_item_id)
            if review is None:
                break
            feedback = review["reason"]
            exploration_pool.append_record(exploration_item_id, f"\n**Exploration review — {review['result']}:** {feedback}\n")
            if review["result"] == "approve_for_experiment":
                experiment_completion = workflow.experiments.queue_exploration_item_for_experiment(exploration_item_id)
                return exploration_item_id, experiment_completion
            if review["result"] == "retire_workgroup":
                break

        exploration_pool.update(exploration_item_id, status="retired")
        return "retire_workgroup"

    async def select_direction(
        self, explorer: ExplorerAgent, checker: CheckerAgent, required_parent_exploration_id: str | None,
    ) -> str | None:
        """Hold the team's selection lock through proposal, Checker review and any rejected attempts."""
        async with self.direction_selection_lock:
            feedback = None
            try:
                for _ in range(self.workflow.config.max_attempts):
                    exploration_item_id = await explorer.propose_direction(feedback, required_parent_exploration_id)
                    if exploration_item_id is None:
                        break
                    review = await checker.review_direction(exploration_item_id)
                    if review is None:
                        self.retire_pending_direction(exploration_item_id, "No decision was submitted before attempts ran out.")
                        break
                    approved, feedback = review
                    if approved:
                        return exploration_item_id
            except BaseException:
                # The MCP submission can complete before its native conversation settles and returns the ID.
                if explorer.current_exploration_item_id is not None:
                    self.retire_pending_direction(explorer.current_exploration_item_id, "Selection interrupted before a decision.")
                raise
        return None

    def retire_pending_direction(self, exploration_item_id: str, reason: str) -> None:
        """Release an unreviewed proposal, preserving any decision already written by the Checker."""
        exploration_pool = self.workflow.exploration_pool
        if exploration_pool.get(exploration_item_id).status == "pending_confirmation":
            exploration_pool.append_record(exploration_item_id, f"\n**Direction review:** {reason}\n")
            exploration_pool.update(exploration_item_id, status="retired", code_workspace_path=None)

    async def decide_next_step_after_experiment(self, group: Workgroup, exploration_item_id: str) -> RoundDecision:
        """Apply the Explorer's decision to the measured item; only a finish request needs Checker approval."""
        explorer = group.member(ExplorerAgent)
        checker = group.member(CheckerAgent)
        exploration_pool = self.workflow.exploration_pool
        feedback = None
        while (decision := await explorer.analyse_experiment_result(exploration_item_id, feedback)) is not None:
            action, reason, publish = decision
            exploration_pool.append_record(exploration_item_id, f"\n**Next action — {action}:** {reason}\n")
            if action == "finish":
                limit = self.workflow.config.max_attempts
                remaining = limit - self.finish_review_attempts[group]
                review = await checker.review_finish(exploration_item_id, reason, attempts_left=remaining)
                if review is None:
                    break
                approved, feedback, attempts_used = review
                verdict = "approved" if approved else "rejected"
                exploration_pool.append_record(exploration_item_id, f"\n**Finish {verdict}:** {feedback}\n")
                if not approved:
                    self.finish_review_attempts[group] += attempts_used
                    if self.finish_review_attempts[group] >= limit:
                        break
                    continue

            # Publishing keeps this checkout as a parent for independent copies. An unpublished,
            # finished item retains its evidence and can hand its workspace to a subsequent round.
            exploration_pool.update(exploration_item_id, status="mature" if publish else "retired")
            if action == "continue_exploration":
                return NewExplorationRound(required_parent_exploration_id=exploration_item_id)
            if action == "start_new_round":
                return NewExplorationRound()
            return "finish"

        exploration_pool.update(exploration_item_id, status="retired")
        return "retire_workgroup"

    def request_direction(self, direction: str) -> None:
        """Accept an independent line of work; a new group will select and review it when capacity permits."""
        self.requested_directions.append(direction)
        self.direction_requested.set()

    async def wait_for_team_quota(self) -> Quota:
        """Wait until the task permits at least one Explorer/Checker pair; startup reserves the actual slots."""
        scheduler = self.workflow.agent_scheduler
        while (quota := scheduler.max_concurrent_workgroups(self.workflow.exploration_roles)) == 0:
            await scheduler.quota_changed.wait()
        return quota

    async def fork_explorers(self, count: int) -> list[Workgroup]:
        """Register and return the new pairs; dispatch starts each Explorer fork and its Checker together."""
        groups = []
        for _ in range(count):
            group = await self.workflow.workgroups.create(workspace_id=self.workspace_id, fork_source=self.seed_explorer)
            suggestion = self.requested_directions.popleft() if self.requested_directions else None
            self.directions_to_select[group] = NewExplorationRound(suggested_direction=suggestion)
            groups.append(group)
        return groups

    @property
    def has_work(self) -> bool:
        """Include sleeping experiments and requested directions even when the current quota is zero."""
        return bool(self.running_steps or self.waiting_for_experiment or self.exploration_items_ready_for_analysis
                    or self.directions_to_select or self.requested_directions)

    async def apply_current_quota(self) -> list[Workgroup] | None:
        """Return runnable groups in priority order, or request a fresh dispatch after releasing native members."""
        scheduler = self.workflow.agent_scheduler
        quota = scheduler.max_concurrent_workgroups(self.workflow.exploration_roles)
        slots = None if quota == "unlimited" else max(0, quota - len(self.running_steps))

        ready = [*self.exploration_items_ready_for_analysis, *self.directions_to_select]
        sleeping = [group for group, _ in self.waiting_for_experiment.values()]
        resident = [group for group in (*ready, *sleeping) if group.agents]

        # A waiting pair keeps both sessions. Only a reduced or changed allocation retires it;
        # an extra direction must wait rather than evict the pair whose report is still outstanding.
        retiring = scheduler.select_workgroup_to_retire(resident, capacity=slots)
        if retiring is not None:
            retiring.fork_source = retiring.member(ExplorerAgent)
            await retiring.close_members()
            return None

        free_slots = None if slots is None else slots - len(resident)
        returning = [group for group in ready if group.agents]
        waiting = [group for group in ready if not group.agents]
        new_groups = len(self.requested_directions)
        if free_slots is not None:
            new_groups = min(new_groups, max(0, free_slots - len(waiting)))
        if new_groups:
            waiting.extend(await self.fork_explorers(new_groups))
        return returning + waiting[:free_slots]

    def assign_work(self, available: list[Workgroup]) -> None:
        """Start one step per selected group, preserving the item and conversation on experiment return."""
        for group in available:
            exploration_item_id = self.exploration_items_ready_for_analysis.pop(group, None)
            assignment = self.directions_to_select.pop(group) if exploration_item_id is None else exploration_item_id
            step = self.run_exploration_steps(group, assignment)
            self.running_steps[self.tasks.create_task(step)] = group

    async def wait_for_progress(self, quota_changed: asyncio.Event) -> None:
        """Wait for a completed step, a measurement, a new direction or a quota change."""
        signals = [self.tasks.create_task(event.wait()) for event in (quota_changed, self.direction_requested)]
        try:
            await asyncio.wait(
                (*self.running_steps, *self.waiting_for_experiment, *signals), return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for signal in signals:
                signal.cancel()

    async def collect_finished_work(self) -> None:
        """Route completed steps and published reports to the groups that own them."""
        for step in list(self.running_steps):
            if not step.done():
                continue
            group = self.running_steps.pop(step)
            match step.result():
                case (exploration_item_id, experiment_completion):
                    self.waiting_for_experiment[experiment_completion] = group, exploration_item_id
                case NewExplorationRound() as next_round:
                    self.directions_to_select[group] = next_round
                case "finish" | "retire_workgroup":
                    await group.close_members()
                    self.finish_review_attempts.pop(group, None)

        # An external report may already be available when its group's step returns.
        for experiment_completion in list(self.waiting_for_experiment):
            if experiment_completion.done():
                experiment_completion.result()
                group, exploration_item_id = self.waiting_for_experiment.pop(experiment_completion)
                self.exploration_items_ready_for_analysis[group] = exploration_item_id
