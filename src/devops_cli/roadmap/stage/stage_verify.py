"""The verification pass of the stage job: a model reads the plan before the draft opens (#3153).

The deterministic gates of the job (`check_proposal`, `openspec validate`) judge the shape of a
plan and its paths. A reviewer also finds false premises, code that already exists and tests that
prove nothing. The pass sends the issue, the plan and the start of each file that the plan cites
to the model of the task slot `ai.tasks.verification`, and gets findings of the nine defect types
of the golden set (`stage_eval_cases.DefectType`). A reply with another type fails the schema, and
`chat_structured` sends it back once. In the stage job and in its eval the model is an agent: it
also reads the repository with the read tools of the planner, and a quote may come from the answer
of a tool (#3039). The review of refine (`refine_judge`) sends the same request with no tool.

A finding names its place with a structured locator (`Locator`, #5410): a part of the plan
(`proposal`, `design`, `tasks` or `spec`) or the issue, and a section of that part. A finding is
open when the input holds its place (`VerificationInput.holds`) and when its type is in
`OPEN_TYPES` and its `quote` is a text of the input or of a tool answer
(`VerificationInput.contains`), or it reports a placeholder that the request holds (#3264). A
finding on a requirement, a group or a key that the plan does not hold is advice, whatever its
quote: a reviewer can quote a base spec that the plan does not change. Each open finding returns
the plan to the planner (#5059). It does so `roadmap.stage.verify_repair_rounds` times, and once
more for each review that fixes more earlier findings than it adds, up to
`CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` rounds (`repair_round_due`, #3039, #5066,
#5409). An open finding of the last review keeps the plan in
draft with the label `plan/needs-fix` (#3264). Every other finding is advice: the job lists it in
its comment. The pass never merges and never marks a pull request ready. `devops roadmap eval
verify` scores the first review of a plan on the golden set (`stage_verify_eval`).

A review after a repair is a later review (#5409). Its request also holds `earlier`, the open
findings of the review before it, and `answer`, the blocks of lines of the plan that the revision
added or changed (`changed_texts`): the planner fixes a finding at its place or shows in
`feasibility` that it is no defect, so the changed text is its answer. Its reply
(`LaterVerification`) gives each earlier finding the verdict `holds` or `gone`, and a new finding
is open only when the revision holds its place and its quote is in a block of `answer`
(`judge_later`). An earlier finding keeps its locator. A first review keeps the
request, the prompt and the schema that it had before, so the golden set scores the same pass.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_ai.messages import ModelRequest, UserPromptPart

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
    CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.pull_form import is_placeholder
from devops_cli.roadmap.refine.refine_investigation import tokens_of, tool_stop
from devops_cli.roadmap.stage.stage_change import capability_name, safe_text
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient

_VERIFY_TASK: Final[str] = "roadmap_stage_verify.md"
_VERIFY_TOOLS_TASK: Final[str] = "roadmap_stage_verify_tools.md"
# The rules of a later review, which follow the prompt of the pass only in a later review (#5409).
_VERIFY_LATER_TASK: Final[str] = "roadmap_stage_verify_later.md"
# The opcodes of `SequenceMatcher` that give lines of the revision that the plan before it lacks.
_CHANGED_OPCODES: Final[frozenset[str]] = frozenset({"replace", "insert"})
# The line number that a tool puts before a line of its answer: `12: text` or `src/a.py:12:text`.
_ANSWER_LINE_PREFIX: Final[re.Pattern[str]] = re.compile(r"^(?:[^\s:]+:)?\d+:\s?", re.MULTILINE)
# A reply that fails the schema goes back to the model once, as every reply of the stage job does.
_REPLY_RETURNS: Final[int] = 1
# The types of an open finding when it quotes its evidence: the finding returns the plan to the
# planner, and, in the last review, keeps the plan in draft. A finding that reports a placeholder is
# open too (#3264). `task_order` and `verify_form` came with #3039, `spec_delta_wrong` with #3264
# and `criterion_dropped` with #3448. Each open finding returns the plan (#5059): an open finding
# that the planner never sees keeps the draft with `plan/needs-fix`, and no job repairs it.
OPEN_TYPES: Final[frozenset[DefectType]] = frozenset(
    {
        DefectType.MISSING_PATH,
        DefectType.FALSE_PREMISE,
        DefectType.IGNORES_EXISTING_CODE,
        DefectType.TASK_ORDER,
        DefectType.VERIFY_FORM,
        DefectType.SPEC_DELTA_WRONG,
        DefectType.CRITERION_DROPPED,
    }
)
# The nine types that the verification prompt and reply schema name.
VERIFY_TYPES: Final[frozenset[DefectType]] = OPEN_TYPES | {
    DefectType.CONTRIVED_TEST,
    DefectType.OTHER,
}
# The label of a plan pull request with an open finding (#3264).
PLAN_NEEDS_FIX_LABEL: Final[str] = "plan/needs-fix"
# The keys of a group of the plan that name files.
_FILE_KEYS: Final[tuple[str, ...]] = ("reads", "changes")
# The keys of the plan that the task groups and the spec delta hold. Each other key of the plan,
# such as `why`, `feasibility` or `decisions`, or a key of a proposal of refine, is a key of the
# proposal or the design (#5410). The design holds `decisions` and `rejected`, but a section of
# either file is a key of both: a finding that names the wrong file of the two keeps its place.
_GROUPS_KEY: Final[str] = "groups"
_SPECS_KEY: Final[str] = "specs"
_NOT_FILE_KEYS: Final[frozenset[str]] = frozenset({_GROUPS_KEY, _SPECS_KEY})
# The keys of the plan that hold acceptance criteria: `criteria` of a stage plan and
# `acceptance_criteria` of a proposal of refine.
_CRITERIA_KEYS: Final[tuple[str, ...]] = ("criteria", "acceptance_criteria")
# The keys of an entry of the spec delta that name a requirement, and the key of its scenarios.
_REQUIREMENT_KEYS: Final[tuple[str, ...]] = ("added", "modified", "removed", "renamed")
_NAME_KEYS: Final[tuple[str, ...]] = ("name", "from_name", "to_name")
_SCENARIOS_KEY: Final[str] = "scenarios"
# A task group as a finding names it: its number from 1, with `group`, `task` or both before it,
# the number of a task and a title after it, such as `2`, `group 2: Title`, `task 2.1` or
# `task group 2`.
_GROUP_NUMBER: Final[re.Pattern[str]] = re.compile(r"(?:(?:task|group)s?\s*)*(\d+)(?:\.\d+)?\b")
# The marks that a model may put around a name that it copies.
_NAME_MARKS: Final[str] = "`'\" "
# A word of a name: letters and digits. So `_`, `-`, `#`, `:` and a mark split words and count for
# nothing, and `existing_tool` and `## Existing Tool Considered` share the words `existing tool`.
_WORD: Final[re.Pattern[str]] = re.compile(r"[^\W_]+")


class PlanPart(StrEnum):
    """The part that a finding names (#5410): a file of the plan, its spec delta or the
    issue."""

    PROPOSAL = "proposal"
    DESIGN = "design"
    TASKS = "tasks"
    SPEC = "spec"
    ISSUE = "issue"


class Locator(BaseModel):
    """The place of a finding (#5410). `section` is a key of the plan for the proposal or the
    design (such as `feasibility` or `decisions`) or a text of that part, the number of a task
    group, the name of a requirement of the spec delta, or a text of the issue such as an
    acceptance criterion. `capability` names the capability of the requirement, for the part
    `spec` only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: PlanPart
    section: str = Field(min_length=1)
    capability: str = ""

    @field_validator("capability")
    @classmethod
    def _check_capability(cls, value: str) -> str:
        """An empty capability, or the name of a capability as a spec delta writes it: so the
        comment line holds no space and no bracket in it, and `fix-plan` reads the line back."""
        return value and capability_name(value)

    def text(self) -> str:
        """The place as a comment line shows it: the part, the capability when it has one, and
        the section in brackets."""
        texts = MESSAGES.roadmap
        if self.capability:
            return texts.stage_finding_where_capability.format(
                part=self.part.value, capability=self.capability, section=self.section
            )
        return texts.stage_finding_where.format(part=self.part.value, section=self.section)


class Finding(BaseModel):
    """One defect that the model found in a plan. `where` is the part of the plan or of the
    issue that holds the defect. `quote` is a text of the issue, the plan or a cited file that
    shows the defect, or empty when no text shows it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: DefectType
    where: Locator
    problem: str = Field(min_length=1)
    quote: str = ""

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: DefectType) -> DefectType:
        if value not in VERIFY_TYPES:
            raise ValueError(f"type must be one of {sorted(k.value for k in VERIFY_TYPES)}")
        return value


class Verification(BaseModel):
    """The reply of the pass: the findings, none for a plan with no defect."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(default_factory=list)


class Verdict(StrEnum):
    """What a later review says of an earlier open finding: the revision still `holds` the defect,
    or the defect is `gone` (#5409)."""

    HOLDS = "holds"
    GONE = "gone"


class EarlierVerdict(BaseModel):
    """The verdict of a later review on the earlier finding with the `number` of `earlier`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(ge=1)
    verdict: Verdict


class LaterVerification(BaseModel):
    """The reply of a later review (#5409): one verdict for each earlier finding, and the new
    findings. The key `earlier` is required, so a reply with no verdict goes back once."""

    model_config = ConfigDict(extra="forbid")

    earlier: list[EarlierVerdict]
    findings: list[Finding] = Field(default_factory=list)


@dataclass(frozen=True)
class Judgement:
    """What one review made of a plan: `findings`, each finding of its reply, and `open`, the
    findings that return the plan. `fixed` holds the earlier open findings that a later review
    marked `gone`, and `added` the open findings that are no earlier finding. For a first review,
    `fixed` is empty and `added` is `open`."""

    findings: tuple[Finding, ...]
    open: tuple[Finding, ...]
    fixed: tuple[Finding, ...] = ()
    added: tuple[Finding, ...] = ()


def _folded(text: str) -> str:
    """`text` with each run of white space as one space, so a quote survives a line break."""
    return " ".join(text.split())


def _name(text: str) -> str:
    """`text` as a name to compare: white space folded, no mark around it, and in one case."""
    return _folded(text).strip(_NAME_MARKS).casefold()


def _phrase(text: str) -> str:
    """The words of `text` in one case, with one space before and after each word, so that `in`
    compares whole words: ` f401 re import ceiling check `. A text with no word gives ``."""
    words = _WORD.findall(text.casefold())
    return f" {' '.join(words)} " if words else ""


def _within(part: str, whole: str) -> bool:
    """Whether the words of `part` are a run of the words of `whole`. A part with no word is in
    no text."""
    wanted = _phrase(part)
    return bool(wanted) and wanted in _phrase(whole)


def _holds_text(texts: Iterable[str], section: str) -> bool:
    """Whether a text of `texts` holds the words of `section`."""
    return any(_within(section, text) for text in texts)


def _holds_key(plan: Mapping[str, Any], keys: Iterable[str], section: str) -> bool:
    """Whether `section` holds the words of one of `keys` that `plan` has, such as `What Changes`
    or `## Existing Tool Considered` for `existing_tool`, or is a text of the value of such a
    key."""
    present = [key for key in keys if key in plan]
    return any(_within(key, section) for key in present) or _holds_text(
        _strings([plan[name] for name in present]), section
    )


def _holds_group(groups: Any, section: str) -> bool:
    """Whether `section` names a group of `groups`: its number from 1 at the start, or the words
    of its title."""
    if not isinstance(groups, list):
        return False
    number = _GROUP_NUMBER.match(_name(section))
    if number is not None:
        return 1 <= int(number[1]) <= len(groups)
    titles = (group.get("title") for group in groups if isinstance(group, Mapping))
    return any(isinstance(title, str) and _within(title, section) for title in titles)


def _delta_names(spec: Mapping[str, Any]) -> list[str]:
    """The names of the requirements that the delta of one capability adds, modifies, removes
    or renames, with each rename by its old and its new name, and the names of their
    scenarios."""
    entries = [
        entry
        for key in _REQUIREMENT_KEYS
        for entry in spec.get(key) or ()
        if isinstance(entry, Mapping)
    ]
    scenarios = [
        scenario
        for entry in entries
        for scenario in entry.get(_SCENARIOS_KEY) or ()
        if isinstance(scenario, Mapping)
    ]
    return [
        item[key]
        for item in (*entries, *scenarios)
        for key in _NAME_KEYS
        if isinstance(item.get(key), str)
    ]


def _same_capability(named: str, capability: str) -> bool:
    """Whether `named` names `capability`: the shorter of the two paths is the end of the longer,
    by whole segments. So `openspec/specs/roadmap-stage/verification` and `verification` name
    `roadmap-stage/verification`, and `ci-gate` does not name `ci-gate-admission`."""
    first, second = (tuple(_name(path).strip("/").split("/")) for path in (named, capability))
    shorter, longer = sorted((first, second), key=len)
    return all(shorter) and longer[len(longer) - len(shorter) :] == shorter


def _holds_requirement(specs: Any, place: Locator) -> bool:
    """Whether the spec delta `specs` holds the requirement that `place` names, in the capability
    of `place` or, when it names none, in any capability. The words of the section hold the words
    of the name of a requirement or a scenario of the delta, or the reverse, so `Requirement:
    <name>.` and a name with its last word cut both name it. A section that names the capability
    itself names its whole delta."""
    for spec in specs if isinstance(specs, list) else ():
        if not isinstance(spec, Mapping):
            continue
        capability = str(spec.get("capability", ""))
        if place.capability and not _same_capability(place.capability, capability):
            continue
        if _same_capability(place.section, capability) or any(
            _within(name, place.section) or _within(place.section, name)
            for name in _delta_names(spec)
        ):
            return True
    return False


def _strings(value: Any) -> Iterator[str]:
    """Every text in a JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, Sequence):
        for item in value:
            yield from _strings(item)


def cited_paths(plan: Mapping[str, Any]) -> list[str]:
    """The paths that the groups of `plan` read or change, each once, in plan order. A plan that
    is not well formed names fewer paths, never fails."""
    groups = plan.get("groups")
    found: dict[str, None] = {}
    for group in groups if isinstance(groups, list) else ():
        for key in _FILE_KEYS:
            names = group.get(key) if isinstance(group, Mapping) else None
            found.update(dict.fromkeys(name for name in names or () if isinstance(name, str)))
    return list(found)


def _read(root: Path, name: str) -> str | None:
    """The start of file `name` of the checkout, with a secret masked, or None when it is no file inside
    the checkout."""
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return mask_secrets(truncate_to_token_limit(text, CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS))


def _plan_lines(plan: Mapping[str, Any]) -> list[str]:
    """Each line of each text of `plan`, in plan order, with its white space folded, and no empty
    line."""
    return [line for text in _strings(plan) for line in map(_folded, text.splitlines()) if line]


def changed_texts(previous: Mapping[str, Any], plan: Mapping[str, Any]) -> tuple[str, ...]:
    """The text of `plan` that the plan `previous` does not hold at its place: each block of
    lines that a `replace` or an `insert` of `difflib.SequenceMatcher` gives, so a line that moved
    is changed text, and a pure delete gives none (#5409)."""
    old, new = _plan_lines(previous), _plan_lines(plan)
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    return tuple(
        "\n".join(new[start:end])
        for tag, _, _, start, end in matcher.get_opcodes()
        if tag in _CHANGED_OPCODES
    )


def cited_files(source: Path, plan: Mapping[str, Any]) -> dict[str, str]:
    """The start of each file that `plan` cites and the checkout `source` has, at most
    `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` of them. A path that is no file inside the checkout is
    left out: the gates judge a missing path."""
    root = source.resolve()
    files: dict[str, str] = {}
    for name in cited_paths(plan):
        if len(files) == CONST_ROADMAP_STAGE_VERIFY_MAX_FILES:
            break
        text = _read(root, name)
        if text is not None:
            files[name] = text
    return files


@dataclass(frozen=True)
class VerificationInput:
    """What the model reads: the issue, the plan and the cited files, and after an agent run,
    `reads`, the answers of its tools. A later review also reads `earlier`, the open findings of
    the review before it, and `answer`, the text of the plan that the revision changed (#5409)."""

    number: int
    title: str
    body: str
    plan: Mapping[str, Any]
    files: Mapping[str, str]
    reads: tuple[str, ...] = ()
    earlier: tuple[Finding, ...] = ()
    answer: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        *,
        number: int,
        title: str,
        body: str,
        plan: Mapping[str, Any],
        source: Path,
        window: int | None = None,
        earlier: Sequence[Finding] = (),
        previous: Mapping[str, Any] | None = None,
    ) -> VerificationInput:
        """The input for `plan` of issue `number`, with the cited files read from `source`. With
        `window`, the context window of the model that serves the run in tokens, the request keeps
        the first cited files, in plan order, that leave the tools room to read (#3039): with its
        instructions, the request stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below the point
        where the run offers no more tools (`tool_stop`). With `earlier`, the open findings of the
        review of `previous`, the plan before the repair, the input is that of a later review, and
        `answer` holds the text of `plan` that `previous` does not hold (#5409)."""
        text = truncate_to_token_limit(body, CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS)
        found = tuple(earlier)
        answer = changed_texts(previous or {}, plan) if found else ()
        files = cited_files(source, plan)
        if window is not None:
            base = cls(number, title, text, plan, {}, earlier=found, answer=answer)
            limit = tool_stop(window) - CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS
            files = _fitting(files, base, limit)
        return cls(number, title, text, plan, files, earlier=found, answer=answer)

    def with_reads(self, answers: Iterable[str]) -> VerificationInput:
        """This input with the tool `answers` of the run, which a quote may also come from."""
        return replace(self, reads=tuple(answers))

    def text(self) -> str:
        """The request as the text that the model reads: the JSON document of `payload`."""
        return json.dumps(self.payload(), ensure_ascii=False, indent=1)

    def payload(self) -> dict[str, Any]:
        """The request as the JSON document that the prompt describes. Only a later review has
        the keys `earlier`, each earlier open finding with its number, and `answer`."""
        payload: dict[str, Any] = {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "plan": dict(self.plan),
            "files": dict(self.files),
        }
        if self.earlier:
            payload["earlier"] = [
                {"number": number, **finding.model_dump(mode="json")}
                for number, finding in enumerate(self.earlier, 1)
            ]
            payload["answer"] = list(self.answer)
        return payload

    def system(self) -> str:
        """The system prompt of the review of this input: the pass, and for a later review the
        rules of a later review after it."""
        prompt = load_task_prompt(_VERIFY_TASK)
        return f"{prompt}\n\n{load_task_prompt(_VERIFY_LATER_TASK)}" if self.earlier else prompt

    def in_answer(self, quote: str) -> bool:
        """Whether `quote`, with white space folded, is in a block of `answer`."""
        wanted = _folded(quote)
        return bool(wanted) and any(wanted in _folded(text) for text in self.answer)

    def request_texts(self) -> Iterable[str]:
        """The texts of the request."""
        yield from (self.title, self.body)
        yield from _strings(self.plan)
        yield from self.files.values()

    def texts(self) -> Iterable[str]:
        """The texts that a quote may come from: the request and each tool answer, as the tool
        gave it and with no line numbers, so a quote can span lines of a file."""
        yield from self.request_texts()
        for answer in self.reads:
            yield answer
            yield _ANSWER_LINE_PREFIX.sub("", answer)

    def contains(self, quote: str) -> bool:
        """Whether `quote`, with white space folded, is in a text that a quote may come from. An
        empty quote is in none."""
        wanted = _folded(quote)
        return bool(wanted) and any(wanted in _folded(text) for text in self.texts())

    def requests(self, quote: str) -> bool:
        """Whether `quote`, with white space folded, is in a text of the request."""
        wanted = _folded(quote)
        return bool(wanted) and any(wanted in _folded(text) for text in self.request_texts())

    def holds(self, place: Locator) -> bool:
        """Whether the plan or the issue of the request holds `place` (#5410). The names compare
        by their words, in one case, so a mark, a heading sign or a small change of form does not
        lose a place. A group is a number of `groups` or the title of one. A requirement is a name
        of a requirement or a scenario that the spec delta of its capability adds, modifies,
        removes or renames. A section of the proposal or the design is a key of either file, or a
        text of their values: a finding that names the wrong file of the two keeps its place. A
        section of the issue is a text of its title, its body or the acceptance criteria of the
        plan. A tool answer holds no place: a reviewer can read a base spec that the plan does not
        change."""
        plan = self.plan
        match place.part:
            case PlanPart.TASKS:
                return _holds_group(plan.get(_GROUPS_KEY), place.section)
            case PlanPart.SPEC:
                return _holds_requirement(plan.get(_SPECS_KEY), place)
            case PlanPart.PROPOSAL | PlanPart.DESIGN:
                return _holds_key(plan, set(plan) - _NOT_FILE_KEYS, place.section)
            case PlanPart.ISSUE:
                criteria = _strings([plan.get(key) or () for key in _CRITERIA_KEYS])
                return _holds_text((self.title, self.body, *criteria), place.section)


def agent_instructions(system: str) -> str:
    """The instructions of an agent run of the pass: `system`, the pass, and the rules of a run
    that has the read tools. They hold no text of the planner."""
    return f"{system}\n\n{load_task_prompt(_VERIFY_TOOLS_TASK)}"


def _request_tokens(given: VerificationInput) -> int:
    """The tokens of the first request of an agent run on `given`, counted as the run counts them
    when it decides to offer its tools."""
    return tokens_of(
        [
            ModelRequest(
                parts=[UserPromptPart(content=given.text())],
                instructions=agent_instructions(given.system()),
            )
        ]
    )


def _fitting(files: Mapping[str, str], base: VerificationInput, limit: int) -> dict[str, str]:
    """The first of `files`, in order, that keep the request of `base` within `limit` tokens. The
    first file that does not fit ends the list, so the kept files are a prefix of the plan order
    (#3039)."""
    kept: dict[str, str] = {}
    for name, text in files.items():
        trial = {**kept, name: text}
        if _request_tokens(replace(base, files=trial)) > limit:
            break
        kept = trial
    return kept


def verify(client: StageClient, given: VerificationInput) -> list[Finding]:
    """The findings of the model for `given`. A reply that fails the schema, such as a finding of
    an unknown type, goes back once, and a second one raises `StructuredOutputValidationError`."""
    reply = client.chat_structured(
        given.system(),
        given.text(),
        Verification,
        max_retries=_REPLY_RETURNS,
    )
    return list(reply.findings)


def verify_later(client: StageClient, given: VerificationInput) -> LaterVerification:
    """The reply of the model to the later review `given`: a verdict for each earlier finding and
    the new findings. A reply that fails the schema goes back once, as in `verify`."""
    return client.chat_structured(
        given.system(),
        given.text(),
        LaterVerification,
        max_retries=_REPLY_RETURNS,
    )


def _reports_placeholder(finding: Finding) -> bool:
    """Whether the quote of `finding` is a placeholder text, such as `placeholder` or `x`."""
    return is_placeholder(finding.quote)


def open_findings(
    findings: Sequence[Finding],
    given: VerificationInput,
    *,
    types: frozenset[DefectType] = OPEN_TYPES,
) -> list[Finding]:
    """The findings that return the plan to the planner and keep it in draft: a finding whose
    place the plan or the issue holds (#5410), with a type of `types` and a quote that is in the
    input or in a tool answer, or with a placeholder that the request holds (#3264, #5059). A
    placeholder in a file that a tool read is no defect of the plan. Any other finding is advice."""
    return [
        f
        for f in findings
        if given.holds(f.where)
        and (
            (f.type in types and given.contains(f.quote))
            or (_reports_placeholder(f) and given.requests(f.quote))
        )
    ]


def judge_later(
    reply: LaterVerification,
    given: VerificationInput,
    *,
    types: frozenset[DefectType] = OPEN_TYPES,
) -> Judgement:
    """What the later review `reply` made of the plan of `given` (#5409). An earlier finding that
    the reply marks `holds`, gives no verdict, or reports again as a new finding stays open as it
    is, with its locator: the review that opened it checked its quote and its place (#5410). Any
    other earlier finding that it marks `gone` is fixed, but not a finding that it also marks
    `holds`. So a reply that breaks the rules keeps a finding and never closes one. A new finding
    is open only when `open_findings` opens it, so the revision holds its place, and its quote is
    in a block of `answer`, the text that the revision changed. Any other new finding is advice,
    and a new finding that is an earlier one adds nothing."""
    holds = {entry.number for entry in reply.earlier if entry.verdict is Verdict.HOLDS}
    gone = {entry.number for entry in reply.earlier if entry.verdict is Verdict.GONE} - holds
    fixed = tuple(
        finding
        for number, finding in enumerate(given.earlier, 1)
        if number in gone and finding not in reply.findings
    )
    held = tuple(finding for finding in given.earlier if finding not in fixed)
    added = tuple(
        dict.fromkeys(
            finding
            for finding in open_findings(reply.findings, given, types=types)
            if given.in_answer(finding.quote) and finding not in given.earlier
        )
    )
    return Judgement(tuple(reply.findings), held + added, fixed, added)


def repair_round_due(round_: int, rounds: int, last: Judgement) -> bool:
    """Whether repair round `round_` (1 for the first) may start after the review `last`. A round
    up to `rounds` (`roadmap.stage.verify_repair_rounds`) may start. A later round may start only
    while `last` fixed more earlier findings than it added: one review judged both, so the check
    compares no two independent reviews and makes no model call (#5066, #5409). No round passes
    `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING`."""
    if round_ > CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING:
        return False
    if round_ <= rounds:
        return True
    return len(last.fixed) > len(last.added)


def finding_line(finding: Finding) -> str:
    """The line that lists `finding` in a comment: its type, place and problem, and its quote with
    the secrets and the markup of the model's text made safe."""
    quote = (
        MESSAGES.roadmap.stage_finding_quote.format(quote=safe_text(finding.quote))
        if finding.quote.strip()
        else ""
    )
    return MESSAGES.roadmap.stage_finding.format(
        type=finding.type.value,
        where=safe_text(finding.where.text()),
        problem=safe_text(finding.problem),
        quote=quote,
    )


def return_problem(findings: Sequence[Finding]) -> str:
    """The `problem` that sends the plan back to the planner: one line for each finding."""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_verify_return.format(findings=lines)


def findings_section(findings: Sequence[Finding]) -> str:
    """The section of the comment of the job that lists `findings`, or an empty text for none."""
    if not findings:
        return ""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_comment_findings.format(findings=lines)


def open_findings_section(findings: Sequence[Finding]) -> str:
    """The section of the comment that lists the open `findings` first, or an empty text for
    none (#3264)."""
    if not findings:
        return ""
    lines = "\n".join(finding_line(finding) for finding in findings)
    return MESSAGES.roadmap.stage_comment_open_findings.format(findings=lines)


__all__ = [
    "OPEN_TYPES",
    "PLAN_NEEDS_FIX_LABEL",
    "EarlierVerdict",
    "Finding",
    "Judgement",
    "LaterVerification",
    "Locator",
    "PlanPart",
    "Verdict",
    "Verification",
    "VerificationInput",
    "agent_instructions",
    "changed_texts",
    "cited_files",
    "cited_paths",
    "finding_line",
    "findings_section",
    "judge_later",
    "open_findings",
    "open_findings_section",
    "repair_round_due",
    "return_problem",
    "verify",
    "verify_later",
]
