"""The GitHub writes of an implement run, which the phase `publish` makes (#3702).

The agent phase holds no App key, so it writes nothing to GitHub: it gives the data of its run in
`outcome.json`. `RunReport` makes the writes of that run from the data: the stop comment, Status
Blocked and the record of a stop, the owner question, the return to New, the comment of the run on
the pull request, the title, the body and the labels of the draft, and the record and Status of a
run that ended at the draft. The texts are the ones that the run wrote before the phases. The data
comes from a file that the agent phase wrote, so `implement_phases.py` masks and cleans its text
before it reaches this module, and each renderer here masks and fences the agent text as before.
"""

from __future__ import annotations

import json
import textwrap
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS,
    CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
    CONST_ROADMAP_IMPLEMENT_STEPS_FILE,
)
from devops_cli.exceptions import (
    GitHubOperationError,
    GitHubUnauthenticatedError,
    RoadmapImplementError,
)
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.output import print_muted
from devops_cli.roadmap.failure import (
    FailureAction,
    FailureClass,
    FailureEvidence,
    classify_failure,
    failure_lines,
    left_action,
)
from devops_cli.roadmap.fence import code_fence
from devops_cli.roadmap.implement.implement import ImplementTarget
from devops_cli.roadmap.implement.implement_amend import Amendment
from devops_cli.roadmap.implement.implement_limits import new_tokens
from devops_cli.roadmap.implement.implement_run import (
    _MANUAL_RUN,
    _base_status_text,
    _check_log_end,
    _check_section,
    _diff_section,
    _extension_section,
    _outcome_label,
    _plan_defect_question,
    _RecordedSpend,
    _step_label,
    _step_spend,
)
from devops_cli.roadmap.implement.implement_scoped_ci import ScopedResult
from devops_cli.roadmap.implement.implement_shell_policy import shown
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, TierSpend
from devops_cli.roadmap.implement.implement_strength import StrengthReport, report_lines
from devops_cli.roadmap.implement.implement_trace import (
    ImplementTrace,
    SummaryRow,
    last_failing_command,
    summary_table,
)
from devops_cli.roadmap.owner_question import OwnerQuestion
from devops_cli.roadmap.project_profile import ProjectStep
from devops_cli.roadmap.pull_labels import (
    add_pull_labels,
    declared_labels,
    remove_pull_labels,
    stale_labels,
)
from devops_cli.roadmap.return_item import apply_return, plan_return
from devops_cli.roadmap.stage.stage_change import safe_text
from devops_cli.roadmap.status_sync import StatusFacts, write_status
from devops_cli.roadmap.steps.comment import Target, post
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ImplementResult,
    Item,
    OwnerQuestionRecordKey,
    RoadmapStore,
)
from devops_cli.roadmap.title_labels import title_labels
from devops_cli.security.sanitizer import mask_secrets


@dataclass(frozen=True)
class StopFacts:
    """The facts of a stop, as the agent phase gives them and `RunReport.stop` writes them: the
    fields of the stop of a step (`implement_run._StopError`)."""

    step: str
    reason: str
    last_message: str = ""
    push: bool = True
    kept_branch: bool = False
    diff: str = ""
    diff_cut: bool = False
    status: int | None = None
    check: str = ""
    check_log: str = ""
    repair_rounds: int = 0
    tier_changes: int = 0
    failure_class: FailureClass | None = None
    action_left: FailureAction | None = None
    conflict_files: tuple[str, ...] = ()


def spend_json(earlier: _RecordedSpend, outcomes: Sequence[StepOutcome]) -> str:
    """The spend of every step of the item, itemized under the tier that served it (#3060), and
    the input tokens of the first request of each step (#3499): the sum of the earlier Jobs of the
    item and this run (#4070)."""
    tiers: dict[str, dict[str, int]] = {
        tier: spend.model_dump() for tier, spend in earlier.tiers.items()
    }
    for outcome in outcomes:
        for tier, spend in outcome.tier_spend.items():
            held = tiers.setdefault(tier, TierSpend().model_dump())
            held["requests"] += spend.requests
            held["input_tokens"] += spend.input_tokens
            held["cache_read_tokens"] += spend.cache_read_tokens
            held["output_tokens"] += spend.output_tokens
    return json.dumps(
        {
            "requests": earlier.requests + sum(o.requests for o in outcomes),
            "input_tokens": earlier.input_tokens + sum(o.input_tokens for o in outcomes),
            "cache_read_tokens": earlier.cache_read_tokens
            + sum(o.cache_read_tokens for o in outcomes),
            "output_tokens": earlier.output_tokens + sum(o.output_tokens for o in outcomes),
            "new_tokens": earlier.new_tokens + sum(new_tokens(o) for o in outcomes),
            "steps": [*earlier.steps, *(_step_spend(o) for o in outcomes)],
            "tiers": tiers,
        }
    )


@dataclass
class RunReport:
    """The data of one implement run for its GitHub writes: the item and its branch, the draft,
    and what the steps of the run did."""

    store: RoadmapStore
    repo: str
    target: ImplementTarget
    pull: int | None
    outcomes: list[StepOutcome] = field(default_factory=list)
    amendments: list[Amendment] = field(default_factory=list)
    scoped: list[ScopedResult] = field(default_factory=list)
    scoped_notes: list[str] = field(default_factory=list)
    skipped_steps: list[ProjectStep] = field(default_factory=list)
    trace: ImplementTrace = field(default_factory=ImplementTrace)
    strength: StrengthReport | None = None
    conflict_files: tuple[str, ...] = ()
    earlier: _RecordedSpend = field(default_factory=_RecordedSpend)
    _comment_target: Target | None = field(default=None, init=False)

    @property
    def number(self) -> int:
        return self.target.item.number

    def fresh(self) -> Item:
        """The item as it is now: a field write refuses an item read before an earlier write."""
        held = self.store.item(self.number)
        if held is None:
            raise RoadmapImplementError(MESSAGES.roadmap.item_left_not_item)
        return held

    def spend(self) -> str:
        return spend_json(self.earlier, self.outcomes)

    def repair_rounds(self) -> int:
        return sum(o.repair_rounds for o in self.outcomes)

    def passed_group(self) -> dict[Any, str | int | None]:
        """The mark of the last group that passed in the run, or none when no group passed."""
        groups = [o.group for o in self.outcomes if o.group and o.status is StepStatus.DONE]
        return {ImplementRecordKey.GROUP: str(groups[-1])} if groups else {}

    # ── The comment of the run on the pull request ──

    def comment(self, pull: int, *, stopped: str = "") -> None:
        """Write the comment of this run on the pull request: the table of the steps of this Job,
        the amendments, the skipped steps, the scoped runs, the strength and check lines, and the
        notes. A stop gives `stopped`, the line that links the stop comment on the issue (#3997),
        in place of the table (#6194). A run has one comment, that the second line marks with the
        run id (#4070). A Job with nothing to show writes nothing."""
        texts = MESSAGES.roadmap
        table = "" if stopped else summary_table(self._row(outcome) for outcome in self.outcomes)
        skipped_lines = [
            texts.implement_pull_comment_skipped.format(
                step=step.value, file=CONST_ROADMAP_IMPLEMENT_STEPS_FILE
            )
            for step in self.skipped_steps
        ]
        lines = "\n".join(
            [
                *self._tool_lines(),
                *(amendment.line() for amendment in self.amendments),
                *skipped_lines,
                *self._scoped_lines(),
                *(report_lines(self.strength) if self.strength is not None else []),
                *self._check_lines(),
                *self._comment_lines(),
            ]
        )
        body = "\n\n".join(part for part in (stopped, table, lines) if part)
        if not body:
            return
        run = texts.implement_pull_comment_run.format(
            run=self.target.item.job_record.get(ImplementRecordKey.JOB) or _MANUAL_RUN
        )
        comment = texts.implement_pull_comment.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, run=run, lines=body
        )
        client = get_github_session().client
        if self._comment_target is None or self._comment_target.number != pull:
            self._comment_target = Target(self.repo, pull, client=client)
        post(self._comment_target, CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, run, comment)

    def _tool_lines(self) -> list[str]:
        totals: Counter[str] = Counter()
        for outcome in self.outcomes:
            totals.update(outcome.tool_counts)
        if not totals:
            return []
        tools = ", ".join(f"{tool} {count}" for tool, count in totals.most_common())
        return [MESSAGES.roadmap.implement_pull_comment_tools.format(tools=tools)]

    def _comment_lines(self) -> list[str]:
        names = dict.fromkeys(name for outcome in self.outcomes for name in outcome.comments)
        if not names:
            return []
        return [MESSAGES.roadmap.implement_pull_comments_used.format(names=", ".join(names))]

    def _check_lines(self) -> list[str]:
        texts = MESSAGES.roadmap
        lines: list[str] = []
        for outcome in self.outcomes:
            if (replay := outcome.fail_to_pass) is not None:
                lines.append(
                    texts.implement_pull_fail_to_pass.format(
                        group=outcome.group,
                        status=_base_status_text(replay.status),
                        failed=", ".join(replay.failed) or texts.implement_pull_fail_to_pass_none,
                    )
                )
                continue
            lines.extend(
                texts.implement_pull_verified.format(
                    group=outcome.group,
                    command=check.command,
                    status=check.status,
                    fence=code_fence(check.output),
                    output=check.output,
                )
                for check in outcome.verified
            )
        return lines

    def _scoped_lines(self) -> list[str]:
        texts = MESSAGES.roadmap
        runs = [
            texts.implement_pull_comment_scoped.format(
                name=result.name,
                result=texts.implement_scoped_passed
                if result.passed
                else texts.implement_scoped_failed,
                seconds=result.seconds,
            )
            for result in self.scoped
        ]
        notes = [
            texts.implement_pull_comment_scoped_note.format(note=note) for note in self.scoped_notes
        ]
        return [*runs, *notes]

    def _row(self, outcome: StepOutcome) -> SummaryRow:
        step = _outcome_label(outcome)
        return SummaryRow(
            step=step,
            status=outcome.status.value,
            attempts=1 + outcome.repair_rounds,
            tokens_in=outcome.input_tokens,
            tokens_out=outcome.output_tokens,
            command=last_failing_command(self.trace.events, step),
        )

    def _stop_table(self, stop: StopFacts) -> str:
        rows = [self._row(outcome) for outcome in self.outcomes]
        failing = last_failing_command(self.trace.events, stop.step, stop.check)
        if rows and rows[-1].step == stop.step and self.outcomes[-1].status is StepStatus.STOPPED:
            rows[-1] = replace(rows[-1], command=failing)
        else:
            rows.append(
                SummaryRow(
                    step=stop.step,
                    status=StepStatus.STOPPED.value,
                    attempts=1 + stop.repair_rounds,
                    tokens_in=0,
                    tokens_out=0,
                    command=failing,
                )
            )
        return summary_table(rows)

    # ── The draft ──

    def delivery_metadata(self, pull: int, title: str, body: str) -> None:
        """Set the title and the body of the draft `pull` and replace its labels with the labels
        of the title (#2714, #3215). A label write that GitHub refuses gets a comment on the pull
        request and leaves the title and the body."""
        texts = MESSAGES.roadmap
        client = get_github_session().client
        before = client.get_pull(self.repo, pull)
        client.update_pull(self.repo, pull, title=title, body=body)
        try:
            declared = declared_labels(self.store, ref=None)
            old = title_labels(before.title, declared)
            new = title_labels(title, declared)
            stale = list(stale_labels(before.labels, old, new))
            if new.type_label:
                for label in before.labels:
                    if label.startswith("type/") and label != new.type_label and label not in stale:
                        stale.append(label)
            add_pull_labels(self.store, pull, new.labels)
            remove_pull_labels(self.store, pull, tuple(stale))
        except GitHubUnauthenticatedError:
            raise
        except GitHubOperationError as exc:
            note = texts.implement_pull_labels_failed.format(error=exc)
            post(
                Target(self.repo, pull, client=client),
                CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                f"labels-failed-{pull}",
                f"{CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER}\nlabels-failed-{pull}\n\n{note}",
            )

    def end_drafted(self, pull: int, sha: str) -> None:
        """End the run at the draft pull request `pull`, whose head is `sha` (#6559): record the
        result `drafted`, set Status In Review and comment the spend on the item."""
        marks: dict[Any, str | int | None] = {
            **self.passed_group(),
            ImplementRecordKey.SHA: sha,
            ImplementRecordKey.PR: str(pull),
            ImplementRecordKey.SPEND: self.spend(),
            ImplementRecordKey.TRACE: self.trace.encode(),
            ImplementRecordKey.REPAIR_ROUNDS: self.repair_rounds(),
            ImplementRecordKey.CHECKED_SHA: None,
            ImplementRecordKey.PUBLISHED_SHA: None,
            ImplementRecordKey.BASE: None,
            ImplementRecordKey.RESULT: ImplementResult.DRAFTED.value,
        }
        write_status(self.store, self.fresh(), StatusFacts(pull_ready=True), marks=marks)
        spend = json.loads(self.spend())
        self.store.comment(
            self.number,
            MESSAGES.roadmap.implement_comment_finished.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
                pull=pull,
                extensions=_extension_section(spend["steps"]),
                **spend,
            ),
        )

    # ── A claim, a return and a stop ──

    def yield_to(self, owner: str, boundary: str) -> None:
        """Tell the item why the run ended: an agent or a person holds it. Nothing is pushed, and
        the Status and the owner stay as the new owner has them."""
        self.store.comment(
            self.number,
            MESSAGES.roadmap.implement_comment_claimed.format(
                marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, owner=owner, boundary=boundary
            ),
        )
        self.store.set_marks(
            self.fresh(), {ImplementRecordKey.RESULT: ImplementResult.YIELDED.value}
        )

    def return_to_new(self, template: str, evidence: str) -> None:
        """Return the item to New with a comment of `template`, whose evidence, text of the agent,
        goes in a fence, and clear the record of the run. The spend stays, so the report of the Job
        counts the tokens of the run (#5881)."""
        evidence = mask_secrets(evidence.strip())[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS]
        fence = code_fence(evidence)
        comment = template.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER, evidence=f"{fence}\n{evidence}\n{fence}"
        )
        apply_return(self.store, plan_return(self.store, self.number, comment, self.repo))
        self.store.set_marks(
            self.fresh(),
            {
                ImplementRecordKey.GROUP: None,
                ImplementRecordKey.SHA: None,
                ImplementRecordKey.BRANCH: None,
                ImplementRecordKey.PR: None,
                ImplementRecordKey.BASE: None,
                ImplementRecordKey.PLAN_SUMMARY: None,
                ImplementRecordKey.SPEND: self.spend(),
                ImplementRecordKey.CHECKED_SHA: None,
                ImplementRecordKey.PUBLISHED_SHA: None,
                ImplementRecordKey.RESULT: ImplementResult.RETURNED.value,
            },
        )

    def stop(self, stop: StopFacts, note: str) -> None:
        """Tell the item why the run stopped, set it Blocked, and record the step. `note` says what
        `publish` pushed of the groups that passed, or why the push failed (#3645, #6194)."""
        texts = MESSAGES.roadmap
        last = safe_text(mask_secrets(stop.last_message))[
            :CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS
        ]
        reason = textwrap.indent(
            mask_secrets(stop.reason).strip()[:CONST_ROADMAP_IMPLEMENT_REASON_CHARS], "    "
        )
        klass = (
            stop.failure_class
            if stop.failure_class is not None
            else classify_failure(
                FailureEvidence(
                    text=stop.reason,
                    exit_status=stop.status,
                    check=stop.check,
                    log=stop.check_log,
                )
            )
        )
        check = shown(
            mask_secrets(stop.check or last_failing_command(self.trace.events, stop.step) or ""),
            CONST_ROADMAP_IMPLEMENT_REASON_CHARS,
        )
        check_log = _check_log_end(stop.check_log)
        question = (
            _plan_defect_question(stop.step, check, self.target.item.url)
            if klass is FailureClass.PLAN_DEFECT
            else None
        )
        taken: FailureAction | None = None
        if stop.tier_changes:
            taken = FailureAction.CHANGE_TIER
        elif stop.repair_rounds:
            taken = FailureAction.REPAIR
        elif any(_step_label(a.group) == stop.step for a in self.amendments):
            taken = FailureAction.AMEND
        left = stop.action_left if stop.action_left is not None else left_action(klass, taken)
        spend = self.spend()
        print_muted(
            texts.implement_failure_trace.format(failure_class=klass.value, left=left.value)
        )
        question_marks = self._ask(question)
        stopped = texts.implement_comment_stopped.format(
            marker=CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
            step=stop.step,
            check=_check_section(check, check_log),
            failure=failure_lines(
                klass,
                repair_rounds=stop.repair_rounds,
                taken=taken,
                left=left,
                tier_changes=stop.tier_changes,
            ),
            table=self._stop_table(stop),
            extensions=_extension_section(json.loads(spend)["steps"]),
            reason=reason,
            last=last or texts.implement_comment_last_none,
            diff=_diff_section(stop),
            note=note,
        )
        posted = self.store.comment(self.number, stopped)
        if self.pull is not None:
            self.comment(
                self.pull,
                stopped=texts.implement_pull_comment_stopped.format(
                    step=stop.step, issue=self.number, url=posted.url or self.target.item.url
                ),
            )
        conflict = stop.conflict_files or self.conflict_files
        marks: dict[Any, str | int | None] = {
            **self.passed_group(),
            ImplementRecordKey.STOPPED: stop.step,
            ImplementRecordKey.FAILURE: klass.value,
            ImplementRecordKey.LEFT_ACTION: left.value,
            ImplementRecordKey.CHECK: check or None,
            ImplementRecordKey.CHECK_LOG: check_log or None,
            ImplementRecordKey.CONFLICT: json.dumps(list(conflict)) if conflict else None,
            ImplementRecordKey.SPEND: spend,
            ImplementRecordKey.TRACE: self.trace.encode(),
            ImplementRecordKey.REPAIR_ROUNDS: self.repair_rounds() + stop.repair_rounds,
        }
        if self.pull is not None:
            marks[ImplementRecordKey.PR] = str(self.pull)
        marks.update(question_marks)
        marks[ImplementRecordKey.RESULT] = ImplementResult.STOPPED.value
        write_status(self.store, self.fresh(), StatusFacts(stopped=True), marks=marks)

    def _ask(self, question: OwnerQuestion | None) -> dict[Any, str | int | None]:
        """Post the owner-question frame of a stop that needs an owner decision, and give the marks
        that record it (#3077). No question gives no mark."""
        if question is None:
            return {}
        self.store.comment(self.number, question.render())
        return {
            OwnerQuestionRecordKey.HASH: question.hash,
            OwnerQuestionRecordKey.TEXT: question.question,
            OwnerQuestionRecordKey.ANSWER: None,
        }


__all__ = ["RunReport", "StopFacts", "spend_json"]
