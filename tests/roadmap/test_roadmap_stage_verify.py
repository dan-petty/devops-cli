"""The verification pass of the stage job: its input, its findings and the quote rule (#3153)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

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
)
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.refine_investigation import tool_stop
from devops_cli.roadmap.stage_eval_cases import DefectType, load_cases
from devops_cli.roadmap.stage_toolbox import ToolboxClient, review
from devops_cli.roadmap.stage_verify import (
    OPEN_TYPES,
    PLAN_NEEDS_FIX_LABEL,
    RETURN_TYPES,
    Finding,
    Verification,
    VerificationInput,
    agent_instructions,
    cited_paths,
    findings_section,
    open_findings,
    open_findings_section,
    return_problem,
    returning,
    verify,
)
from devops_cli.roadmap.stage_verify import Verification as VerificationReply
from tests.support.scripted_model import Script, call

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

    assert named == {kind.value for kind in DefectType}


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


def test_the_return_types_add_task_order_and_verify_form() -> None:
    assert RETURN_TYPES == {
        DefectType.MISSING_PATH,
        DefectType.FALSE_PREMISE,
        DefectType.IGNORES_EXISTING_CODE,
        DefectType.TASK_ORDER,
        DefectType.VERIFY_FORM,
    }
    given = _input()
    findings = [
        _finding(DefectType.TASK_ORDER, "The job drops the last comment"),
        _finding(DefectType.VERIFY_FORM, "The job drops the last comment"),
    ]

    assert returning(findings, given) == findings
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


def test_a_return_type_with_a_quote_in_the_input_returns_the_plan() -> None:
    given = _input()
    findings = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        _finding(DefectType.MISSING_PATH, "invented quote"),
        _finding(DefectType.CONTRIVED_TEST, "The job drops the last comment"),
        _finding(DefectType.IGNORES_EXISTING_CODE),
    ]

    assert returning(findings, given) == [findings[0]]


def test_the_open_types_add_the_spec_delta_to_the_return_types() -> None:
    assert OPEN_TYPES == RETURN_TYPES | {DefectType.SPEC_DELTA_WRONG}
    assert PLAN_NEEDS_FIX_LABEL == "plan/needs-fix"


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

    assert (findings, returning(findings, _input())) == ([finding], [])
    assert (returning(findings, given), open_findings(findings, given)) == ([finding], [finding])


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
