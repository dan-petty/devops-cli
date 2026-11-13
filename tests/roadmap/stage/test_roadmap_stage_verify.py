"""The verification pass of the stage job: its input, its findings and the quote rule (#3153)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, ToolCallPart

from devops_cli.ai.context_budget import count_tokens
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_TOOL_MAX_CALLS,
    CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
    CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING,
)
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.refine.refine_investigation import tool_stop
from devops_cli.roadmap.stage.stage_eval_cases import DefectType, load_cases
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, review
from devops_cli.roadmap.stage.stage_verify import (
    OPEN_TYPES,
    PLAN_NEEDS_FIX_LABEL,
    VERIFY_TYPES,
    Finding,
    Verification,
    VerificationInput,
    agent_instructions,
    cited_paths,
    findings_section,
    open_findings,
    open_findings_section,
    repair_round_due,
    return_problem,
    verify,
)
from devops_cli.roadmap.stage.stage_verify import Verification as VerificationReply
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient

PLAN = {
    "summary": "Stop the job dropping a comment",
    "why": "The job drops the last comment of a thread.",
    "groups": [
        {
            "title": "Keep the last comment",
            "reads": ["src/a.py"],
            "changes": ["src/a.py", "tests/test_a.py", "../outside.py"],
        },
        {"title": "Second", "reads": ["docs/guide.md"], "changes": ["src/a.py", "src/b.py"]},
    ],
}


def _input(root: Path | None = None, plan: dict[str, object] | None = None) -> VerificationInput:
    return VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body="The job drops the last comment.\nIt happens on a long thread.",
        plan=plan or PLAN,
        source=root or Path("/nonexistent"),
    )


def _finding(kind: DefectType, quote: str = "") -> Finding:
    return Finding(type=kind, where="group 1", problem="The plan is wrong.", quote=quote)


def test_the_prompt_names_the_nine_types_and_no_other() -> None:
    line = next(
        line
        for line in load_task_prompt("roadmap_stage_verify.md").splitlines()
        if "nine types" in line
    )

    named = set(re.findall(r"`([a-z_]+)`", line))

    assert len(VERIFY_TYPES) == 9
    assert named == {kind.value for kind in VERIFY_TYPES}


def test_the_missing_path_type_names_a_needed_file_that_the_plan_does_not_change() -> None:
    line = next(
        line
        for line in load_task_prompt("roadmap_stage_verify.md").splitlines()
        if line.startswith("- `missing_path`")
    )

    assert "does not exist" in line
    assert "needs a file that the plan does not change" in line


def test_a_finding_with_a_type_outside_the_nine_is_refused() -> None:
    with pytest.raises(ValidationError, match="type"):
        Verification.model_validate(
            {"findings": [{"type": "style", "where": "x", "problem": "y", "quote": ""}]}
        )
    with pytest.raises(ValidationError, match="type"):
        Verification.model_validate(
            {
                "findings": [
                    {
                        "type": DefectType.PROMPT_KEY_MISSING.value,
                        "where": "x",
                        "problem": "y",
                        "quote": "",
                    }
                ]
            }
        )


def test_the_open_types_are_the_seven_types_that_the_planner_can_fix() -> None:
    assert OPEN_TYPES == {
        DefectType.MISSING_PATH,
        DefectType.FALSE_PREMISE,
        DefectType.IGNORES_EXISTING_CODE,
        DefectType.TASK_ORDER,
        DefectType.VERIFY_FORM,
        DefectType.SPEC_DELTA_WRONG,
        DefectType.CRITERION_DROPPED,
    }
    assert PLAN_NEEDS_FIX_LABEL == "plan/needs-fix"
    given = _input()
    findings = [
        _finding(DefectType.TASK_ORDER, "The job drops the last comment"),
        _finding(DefectType.VERIFY_FORM, "The job drops the last comment"),
    ]

    assert open_findings(findings, given) == findings


def test_the_cited_files_are_the_existing_files_of_reads_and_changes_in_plan_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    for name in ("src/a.py", "docs/guide.md", "src/b.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(f"text of {name}\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("secret\n", encoding="utf-8")

    given = _input(root)

    assert list(given.files) == ["src/a.py", "docs/guide.md", "src/b.py"]
    assert given.files["src/a.py"] == "text of src/a.py\n"


def test_a_long_cited_file_is_cut_to_the_cap(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("word " * 20000, encoding="utf-8")

    given = _input(tmp_path)

    kept = given.files["src/a.py"]
    assert 0 < len(kept) < len("word " * 20000)
    assert len(kept) < CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS * 8


def test_only_the_files_up_to_the_cap_are_read(tmp_path: Path) -> None:
    names = [f"src/f{index}.py" for index in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES + 5)]
    (tmp_path / "src").mkdir()
    for name in names:
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    plan = {"groups": [{"reads": names, "changes": names}]}

    given = _input(tmp_path, plan)

    assert list(given.files) == names[:CONST_ROADMAP_STAGE_VERIFY_MAX_FILES]


def test_a_secret_in_a_cited_file_is_masked(tmp_path: Path) -> None:
    token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(f'TOKEN = "{token}"\n', encoding="utf-8")

    given = _input(tmp_path)

    assert token not in given.files["src/a.py"]


def test_the_payload_holds_the_issue_the_plan_and_the_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    payload = _input(tmp_path).payload()

    assert set(payload) == {"number", "title", "body", "plan", "files"}
    assert (payload["number"], payload["plan"], payload["files"]) == (
        7,
        PLAN,
        {"src/a.py": "x = 1\n"},
    )


def test_a_quote_of_the_issue_the_plan_or_a_file_is_in_the_input(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def keep(comments):\n    return 1\n", encoding="utf-8")

    given = _input(tmp_path)

    assert [
        given.contains(quote)
        for quote in (
            "It happens   on a long thread.",
            "The job drops the last comment of a thread.",
            "def keep(comments):\n    return 1",
            "text that no part holds",
            "",
            "   ",
        )
    ] == [True, True, True, False, False, False]


def test_an_open_type_with_a_quote_in_the_input_is_open() -> None:
    given = _input()
    findings = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        _finding(DefectType.MISSING_PATH, "invented quote"),
        _finding(DefectType.CONTRIVED_TEST, "The job drops the last comment"),
        _finding(DefectType.IGNORES_EXISTING_CODE),
    ]

    assert open_findings(findings, given) == [findings[0]]


def test_an_open_finding_is_a_listed_type_or_a_placeholder_with_a_quote_in_the_input() -> None:
    given = _input(
        plan={"groups": [{"title": "placeholder"}, {"title": "The job drops a comment"}]}
    )
    findings = [
        _finding(DefectType.SPEC_DELTA_WRONG, "The job drops the last comment"),
        _finding(DefectType.OTHER, "placeholder"),
        _finding(DefectType.MISSING_PATH, "invented quote"),
        _finding(DefectType.CONTRIVED_TEST, "The job drops the last comment"),
        _finding(DefectType.OTHER),
    ]

    assert open_findings(findings, given) == [findings[0], findings[1]]


CRITERION = "The stage eval case MUST hold the plan of #3378 and its recorded search evidence."
# The plan of group 4 of #3410: the criterion names a case of the golden set, and the group writes
# only a fixture and a test file. No group changes the code that gives the case its field.
TEST_ONLY_PLAN = {
    "groups": [
        {
            "title": "Read the evidence in the replay",
            "reads": ["src/devops_cli/roadmap/stage/stage_eval_cases.py"],
            "changes": ["tests/roadmap/test_roadmap_stage_eval_cases.py"],
        },
        {
            "title": "Add the case of a move of the stage modules",
            "reads": ["src/devops_cli/roadmap/stage/stage_eval_cases.py"],
            "changes": [
                "tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/facts.json",
                "tests/roadmap/test_roadmap_stage_negative_search.py",
            ],
        },
    ]
}


def _test_only_input() -> VerificationInput:
    return VerificationInput.of(
        number=3410,
        title="fix(roadmap): the stage gate proves a negative search",
        body=f"## Acceptance criteria\n\n- {CRITERION}\n",
        plan=TEST_ONLY_PLAN,
        source=Path("/nonexistent"),
    )


def test_a_dropped_criterion_finding_of_a_test_only_group_with_a_quote_in_the_input_is_open() -> (
    None
):
    given = _test_only_input()
    finding = Finding(
        type=DefectType.CRITERION_DROPPED,
        where="group 2",
        problem="The group writes only a fixture and a test, and no group adds the field.",
        quote=CRITERION,
    )

    assert open_findings([finding], given) == [finding]


def test_a_dropped_criterion_finding_with_no_quote_in_the_input_is_advice() -> None:
    given = _test_only_input()
    invented = Finding(
        type=DefectType.CRITERION_DROPPED,
        where="group 2",
        problem="The group writes only a test.",
        quote="The case MUST hold a field that the issue never names.",
    )
    unquoted = Finding(
        type=DefectType.CRITERION_DROPPED, where="group 2", problem="The group writes only a test."
    )

    assert open_findings([invented, unquoted], given) == []


def test_the_dropped_criterion_type_names_a_test_only_group_and_one_that_delivers() -> None:
    line = next(
        line
        for line in load_task_prompt("roadmap_stage_verify.md").splitlines()
        if line.startswith("- `criterion_dropped`")
    )

    assert "changes only test files" in line
    assert "no group of the plan changes the code" in line
    assert "when an earlier group changes that code" in line
    assert "is no `criterion_dropped`" in line


def test_the_open_findings_section_lists_each_open_finding_first() -> None:
    finding = _finding(DefectType.OTHER, "placeholder")

    section = open_findings_section([finding])

    assert PLAN_NEEDS_FIX_LABEL in section
    assert "placeholder" in section
    assert open_findings_section([]) == ""


def test_the_problem_that_goes_back_to_the_planner_names_each_finding() -> None:
    problem = return_problem([_finding(DefectType.FALSE_PREMISE, "The job drops the last comment")])

    assert "false_premise" in problem
    assert "group 1" in problem
    assert "The job drops the last comment" in problem


def test_the_findings_section_is_empty_without_findings() -> None:
    assert findings_section([]) == ""


def test_the_findings_section_puts_each_finding_on_one_line_without_a_ping() -> None:
    finding = Finding(
        type=DefectType.CONTRIVED_TEST,
        where="group 2",
        problem="The test\nasks @octocat to read https://example.com/x.",
        quote="a  quote",
    )

    section = findings_section([finding])

    (line,) = [line for line in section.splitlines() if "contrived_test" in line]
    assert "@octocat" not in line.replace("`@octocat`", "")
    assert "group 2" in line
    assert "\n" not in line


# The `why` of a revision of `PLAN`: the planner changed one text in answer to a finding.
REVISED_WHY = "The job keeps the last comment of a thread."


def _later_input(earlier: list[Finding]) -> VerificationInput:
    """The input of the review of a revision of `PLAN` that changes only its `why`, after a
    review whose open findings were `earlier`."""
    return VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body="The job drops the last comment.\nIt happens on a long thread.",
        plan={**PLAN, "why": REVISED_WHY},
        source=Path("/nonexistent"),
        earlier=earlier,
        previous=PLAN,
    )


class _Recorder:
    """A stage client that records the system prompt, the request and the schema of each
    structured call, and answers `reply`."""

    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str, type[object]]] = []

    def chat_structured(
        self, system: str, prompt: str, schema: type[object], *, max_retries: int
    ) -> object:
        self.calls.append((system, prompt, schema))
        return self.reply


def test_a_later_review_gets_the_earlier_findings_and_the_answer() -> None:
    earlier = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        Finding(
            type=DefectType.TASK_ORDER,
            where="group 2",
            problem="The test comes last.",
            quote="Keep the last comment",
        ),
    ]

    payload = _later_input(earlier).payload()

    assert payload["earlier"] == [
        {
            "number": 1,
            "type": "false_premise",
            "where": "group 1",
            "problem": "The plan is wrong.",
            "quote": "The job drops the last comment",
        },
        {
            "number": 2,
            "type": "task_order",
            "where": "group 2",
            "problem": "The test comes last.",
            "quote": "Keep the last comment",
        },
    ]
    assert payload["answer"] == [REVISED_WHY]
    assert payload["plan"]["why"] == REVISED_WHY


def test_a_new_finding_outside_the_changed_text_is_advice() -> None:
    from devops_cli.roadmap.stage.stage_verify import (
        EarlierVerdict,
        Judgement,
        LaterVerification,
        Verdict,
        judge_later,
    )

    earlier = [_finding(DefectType.FALSE_PREMISE, "The job drops the last comment")]
    given = _later_input(earlier)
    unchanged = _finding(DefectType.FALSE_PREMISE, "It happens on a long thread.")
    changed = _finding(DefectType.MISSING_PATH, "keeps the last   comment")
    reply = LaterVerification(
        earlier=[EarlierVerdict(number=1, verdict=Verdict.GONE)], findings=[unchanged, changed]
    )

    judged = judge_later(reply, given)

    assert given.contains(unchanged.quote)
    assert judged == Judgement(
        findings=(unchanged, changed), open=(changed,), fixed=(earlier[0],), added=(changed,)
    )


def test_an_earlier_finding_with_no_verdict_holds() -> None:
    from devops_cli.roadmap.stage.stage_verify import (
        EarlierVerdict,
        LaterVerification,
        Verdict,
        judge_later,
    )

    earlier = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        _finding(DefectType.TASK_ORDER, "Keep the last comment"),
    ]
    reply = LaterVerification(
        earlier=[
            EarlierVerdict(number=1, verdict=Verdict.GONE),
            EarlierVerdict(number=9, verdict=Verdict.GONE),
        ],
        findings=[earlier[1]],
    )

    judged = judge_later(reply, _later_input(earlier))

    assert (judged.open, judged.fixed, judged.added) == ((earlier[1],), (earlier[0],), ())


def test_an_earlier_finding_that_holds_or_comes_again_stays_open() -> None:
    from devops_cli.roadmap.stage.stage_verify import (
        EarlierVerdict,
        LaterVerification,
        Verdict,
        judge_later,
    )

    earlier = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        _finding(DefectType.TASK_ORDER, "Keep the last comment"),
    ]
    reply = LaterVerification(
        earlier=[
            EarlierVerdict(number=1, verdict=Verdict.HOLDS),
            EarlierVerdict(number=2, verdict=Verdict.GONE),
        ],
        findings=[earlier[1]],
    )

    judged = judge_later(reply, _later_input(earlier))

    # The reply marks the second finding `gone` and reports it again: it stays open, and the
    # repeat adds no finding.
    assert (judged.open, judged.fixed, judged.added) == (tuple(earlier), (), ())


def test_an_earlier_finding_with_both_verdicts_holds() -> None:
    from devops_cli.roadmap.stage.stage_verify import (
        EarlierVerdict,
        LaterVerification,
        Verdict,
        judge_later,
    )

    earlier = [_finding(DefectType.FALSE_PREMISE, "The job drops the last comment")]
    reply = LaterVerification(
        earlier=[
            EarlierVerdict(number=1, verdict=Verdict.GONE),
            EarlierVerdict(number=1, verdict=Verdict.HOLDS),
        ]
    )

    judged = judge_later(reply, _later_input(earlier))

    assert (judged.open, judged.fixed) == (tuple(earlier), ())


def test_a_first_review_keeps_its_request_and_its_prompt() -> None:
    from devops_cli.roadmap.stage.stage_verify import LaterVerification, verify_later

    given = _input()
    first = _Recorder(VerificationReply())
    later = _Recorder(LaterVerification(earlier=[]))
    after = _later_input([_finding(DefectType.FALSE_PREMISE, "The job drops the last comment")])

    verify(cast("StageClient", first), given)
    verify_later(cast("StageClient", later), after)

    prompt = load_task_prompt("roadmap_stage_verify.md")
    assert set(json.loads(given.text())) == {"number", "title", "body", "plan", "files"}
    assert first.calls == [(prompt, given.text(), Verification)]
    (system, request, schema) = later.calls[0]
    assert system == f"{prompt}\n\n{load_task_prompt('roadmap_stage_verify_later.md')}"
    assert (request, schema) == (after.text(), LaterVerification)


def test_a_later_reply_with_no_verdict_list_fails_the_schema() -> None:
    from devops_cli.roadmap.stage.stage_verify import LaterVerification

    with pytest.raises(ValidationError, match="earlier"):
        LaterVerification.model_validate({"findings": []})


def test_the_changed_text_is_each_block_of_new_or_moved_lines() -> None:
    from devops_cli.roadmap.stage.stage_verify import changed_texts

    before = {"why": "Keep it.", "groups": [{"title": "A", "tasks": ["one", "two", "three"]}]}
    after = {
        "why": "Keep it.",
        "groups": [{"title": "A", "tasks": ["two", "one", "three", "four\n  words"]}],
    }

    assert changed_texts(before, after) == ("two", "four\nwords")
    assert changed_texts(before, before) == ()


def test_a_round_past_the_setting_needs_more_fixed_than_added_findings() -> None:
    from devops_cli.roadmap.stage.stage_verify import Judgement

    fixed = _finding(DefectType.FALSE_PREMISE, "fixed")
    added = _finding(DefectType.MISSING_PATH, "added")
    progress = Judgement(findings=(), open=(), fixed=(fixed,), added=())
    even = Judgement(findings=(added,), open=(added,), fixed=(fixed,), added=(added,))
    ceiling = CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING

    assert [
        repair_round_due(1, 2, even),
        repair_round_due(3, 2, progress),
        repair_round_due(3, 2, even),
        repair_round_due(ceiling + 1, ceiling + 1, progress),
    ] == [True, True, False, False]


# The nine read tools of the toolset `base` (#3039): a verification run offers exactly these.
_READ_TOOLS = [
    "list_files",
    "read_file",
    "search_code",
    "git_log",
    "git_show",
    "file_symbols",
    "callers",
    "repo_map",
    "read_spec",
]


class _NoInner:
    """The client of the calls that use no tool. A verification run never reaches it."""

    def chat_structured(self, system: str, prompt: str, schema: type, *, max_retries: int) -> None:
        raise AssertionError("a verification run must not call the client with no tool")


def _distinct_words(count: int) -> str:
    """Text with no repeated word, so that the cap cuts it by tokens."""
    return " ".join(f"word{number}" for number in range(count))


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@pytest.fixture
def verify_checkout(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(root, "config", key, value)
    _git(root, "config", "commit.gpgsign", "false")
    (root / "src" / "sample.py").write_text("def keep(comments):\n    return 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root, _git(root, "rev-parse", "HEAD")


def test_a_verify_run_offers_the_nine_read_tools_and_no_write_tool(
    verify_checkout: tuple[Path, str],
) -> None:
    source, sha = verify_checkout
    script = Script(call("read_file", path="src/sample.py"), VerificationReply())
    client = ToolboxClient(script.model(), _NoInner(), source, sha, toolset="base")

    reply = client.chat_structured("Review the plan.", "{}", VerificationReply, max_retries=1)

    assert (reply, script.tools_offered[0]) == (VerificationReply(), _READ_TOOLS)


def test_a_verify_run_starts_with_the_pass_and_its_request_and_no_planner_message(
    verify_checkout: tuple[Path, str],
) -> None:
    source, sha = verify_checkout
    script = Script(VerificationReply())
    client = ToolboxClient(script.model(), _NoInner(), source, sha)

    client.chat_structured("Review the plan.", '{"number": 7}', VerificationReply, max_retries=1)

    first = [part for message in script.seen[0] for part in message.parts]
    assert ([part.part_kind for part in first], first[-1].content) == (
        ["user-prompt"],
        '{"number": 7}',
    )


def test_a_verify_run_has_the_pass_as_its_instructions_and_no_planner_text(
    verify_checkout: tuple[Path, str],
) -> None:
    source, sha = verify_checkout
    script = Script(VerificationReply())
    client = ToolboxClient(script.model(), _NoInner(), source, sha)

    client.chat_structured("Review the plan.", "{}", VerificationReply, max_retries=1)

    (instructions,) = script.instructions
    assert instructions == agent_instructions("Review the plan.")
    assert load_task_prompt("roadmap_stage_tools.md") not in instructions


def test_the_tool_rules_are_only_in_the_instructions_of_an_agent_run() -> None:
    plain = load_task_prompt("roadmap_stage_verify.md")

    assert ("read-only tools" in plain, "repair round" in plain) == (False, False)
    agent = agent_instructions(plain)
    assert ("read-only tools" in agent, "two repair rounds" in agent) == (True, True)


def test_a_verify_run_that_hits_a_limit_names_the_verification_run(
    verify_checkout: tuple[Path, str],
) -> None:
    source, sha = verify_checkout
    calls = ModelResponse(
        parts=[
            ToolCallPart(tool_name="list_files", args={})
            for _ in range(CONST_ROADMAP_STAGE_TOOL_MAX_CALLS + 1)
        ]
    )
    client = ToolboxClient(Script(calls).model(), _NoInner(), source, sha, toolset="base")

    with pytest.raises(RoadmapStageError, match="The verification run stopped"):
        client.chat_structured("Review the plan.", "{}", VerificationReply, max_retries=1)


def test_a_quote_may_come_from_a_tool_answer_of_the_run(verify_checkout: tuple[Path, str]) -> None:
    source, sha = verify_checkout
    finding = _finding(DefectType.FALSE_PREMISE, "def keep(comments):\n    return 1")
    script = Script(call("read_file", path="src/sample.py"), VerificationReply(findings=[finding]))
    client = ToolboxClient(script.model(), _NoInner(), source, sha)

    findings, given = review(client, _input())

    assert (findings, open_findings(findings, _input())) == ([finding], [])
    assert open_findings(findings, given) == [finding]


def test_a_placeholder_in_a_tool_answer_is_no_open_finding() -> None:
    given = _input().with_reads(["12: placeholder"])
    finding = _finding(DefectType.OTHER, "placeholder")

    assert (given.contains("placeholder"), open_findings([finding], given)) == (True, [])


def test_a_quote_with_a_line_number_or_a_search_path_counts_too() -> None:
    given = _input().with_reads(["12: first line\n13: second line", "src/a.py:7:found text"])

    assert [
        given.contains(quote)
        for quote in ("first line second line", "13: second line", "found text", "no such line")
    ] == [True, True, True, False]


def test_a_full_request_at_the_window_of_the_analysis_task_is_offered_the_tools(
    verify_checkout: tuple[Path, str],
) -> None:
    source, _ = verify_checkout
    names = [f"src/module_{number}.py" for number in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES)]
    for name in names:
        (source / name).write_text(_distinct_words(4000), encoding="utf-8")
    window = 65_536
    given = VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body="The job drops the last comment.",
        plan={"groups": [{"title": "big", "reads": names}]},
        source=source,
        window=window,
    )
    script = Script(call("list_files"), call("list_files"), VerificationReply())
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "files")
    head = _git(source, "rev-parse", "HEAD")
    client = ToolboxClient(script.model(), _NoInner(), source, head, toolset="base", window=window)

    verify(client, given)

    assert (script.tools_offered[0], bool(script.tools_offered[1])) == (_READ_TOOLS, True)
    assert 0 < len(given.files) < len(names)


def test_a_verify_run_records_its_read_in_its_trace(verify_checkout: tuple[Path, str]) -> None:
    source, sha = verify_checkout
    script = Script(call("read_file", path="src/sample.py"), VerificationReply())
    client = ToolboxClient(script.model(), _NoInner(), source, sha)

    client.chat_structured("Review the plan.", "{}", VerificationReply, max_retries=1)

    (trace,) = client.traces
    assert [(record.name, json.loads(record.argument)) for record in trace.tool_calls] == [
        ("read_file", {"path": "src/sample.py"})
    ]


def test_the_cited_files_keep_the_plan_order_within_the_window_less_the_tool_reserve(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    names = [f"src/module_{number}.py" for number in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES)]
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("word " * 4000, encoding="utf-8")
    plan = {"groups": [{"title": "big", "reads": names}]}
    window = 40_000

    given = VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body="The job drops the last comment.",
        plan=plan,
        source=root,
        window=window,
    )

    kept = list(given.files)
    assert count_tokens(given.text()) <= tool_stop(window) - CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS
    assert (0 < len(kept) < len(names), kept) == (True, names[: len(kept)])


def test_the_largest_golden_plan_keeps_its_files_in_plan_order_within_the_window(
    tmp_path: Path,
) -> None:
    case = max(
        load_cases(),
        key=lambda case: count_tokens(json.dumps(case.plan, ensure_ascii=False, indent=1)),
    )
    names = cited_paths(case.plan)
    for name in names:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("word " * 4000, encoding="utf-8")
    window = 40_000

    given = VerificationInput.of(
        number=case.issue,
        title=case.title,
        body=case.issue_body,
        plan=case.plan,
        source=tmp_path,
        window=window,
    )

    kept = list(given.files)
    assert (
        count_tokens(given.text()) <= tool_stop(window) - CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS,
        0 < len(kept) < len(names),
        kept,
    ) == (True, True, names[: len(kept)])
