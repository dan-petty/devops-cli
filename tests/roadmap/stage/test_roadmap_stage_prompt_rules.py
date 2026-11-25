"""`devops roadmap stage`: the prompts of the planner agree with the rules they restate (#3202).

The planner gets no `AGENTS.md`, `CONTRIBUTING.md` or `docs/TESTING.md`, so its prompt is the only
copy of a rule that it reads. A rule that has a machine form (a limit, a key, a form of a command, a
list of paths) is read here from that form, and the prompt must say the same. A rule that has no
machine form has no test here.
"""

from __future__ import annotations

import re
import shlex

import pytest
from pydantic import BaseModel

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS
from devops_cli.core.command_resolver import resolve_devops_argv
from devops_cli.roadmap.stage.stage_change import (
    PURPOSE_MIN_CHARS,
    SUMMARY_MAX_CHARS,
    GroupKind,
    StageConstantClaim,
    StageDecision,
    StageGroup,
    StageProposal,
    StageReference,
    StageRejection,
    StageRemoval,
    StageRename,
    StageRequirement,
    StageScenario,
    StageSpec,
    check_proposal,
    pull_request_body,
    staging_title,
)
from devops_cli.roadmap.stage.stage_criteria import PENDING_PERSON, StageCriterion
from devops_cli.roadmap.stage.stage_form import form_problems
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal, stage_summary_limit
from tests.support.paths import REPO_ROOT

_CHANGE_PROMPT = "roadmap_stage_change.md"
_SPLIT_PROMPT = "roadmap_stage_split.md"
# The prompt of the stage agent on stock `Coder` (#6705): it writes the plan files, so it keeps
# each rule of a plan that holds no key of the JSON reply.
_CODER_PROMPT = "roadmap_stage_coder.md"
_PLAN_PROMPTS = [_CHANGE_PROMPT, _CODER_PROMPT]
_PROMPT = load_task_prompt(_CHANGE_PROMPT)
_CONTRIBUTING = (REPO_ROOT / "CONTRIBUTING.md").read_text("utf-8")
_CONFIG = (REPO_ROOT / "openspec" / "config.yaml").read_text("utf-8")
# The largest issue number that the title has to hold with its lead.
_LARGEST_NUMBER = 999999
_CODE_SPAN = re.compile(r"`([^`]+)`")
# The keys that a sentence lists: `a`, `b` and `c`.
_KEY_LIST = re.compile(r"((?:`\w+`(?:, | and |, and )?)+)")


def _spans(text: str) -> list[str]:
    return _CODE_SPAN.findall(text)


def _keys(text: str) -> set[str]:
    """The names in code spans of a list of keys."""
    return set(_spans(text))


def _reply_section(prompt: str) -> str:
    return prompt.split("The reply has these keys and no other", 1)[1]


# ── The keys of the reply ─────────────────────────────────────────────────────


def test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal() -> None:
    bullets = re.findall(r"^- `(\w+)`:", _reply_section(_PROMPT), flags=re.MULTILINE)

    assert sorted(bullets) == sorted(StageProposal.model_json_schema()["properties"])


@pytest.mark.parametrize(
    "model",
    [
        StageDecision,
        StageRejection,
        StageSpec,
        StageRequirement,
        StageScenario,
        StageCriterion,
        StageReference,
        StageRename,
        StageRemoval,
        StageConstantClaim,
    ],
)
def test_each_list_of_keys_of_the_reply_is_the_fields_of_a_model(
    model: type[BaseModel],
) -> None:
    lists = [_keys(found) for found in _KEY_LIST.findall(_reply_section(_PROMPT)) if found]
    expected = set(model.model_fields)

    assert expected in lists


@pytest.mark.parametrize("task", [_CHANGE_PROMPT, _SPLIT_PROMPT])
def test_the_keys_of_a_group_in_the_prompts_are_the_fields_of_a_group(
    task: str,
) -> None:
    prompt = load_task_prompt(task)
    clause = re.search(r"(?:has|with) these keys:(.*?)\. (?:Every task|A `behavior`)", prompt, re.S)
    assert clause is not None
    keys = [segment.split("`")[1] for segment in clause.group(1).split(";")]

    assert sorted(keys) == sorted(StageGroup.model_fields)


@pytest.mark.parametrize("task", [_CHANGE_PROMPT, _SPLIT_PROMPT, _CODER_PROMPT])
def test_the_prompts_name_the_kinds_of_a_group_as_the_enum_does(task: str) -> None:
    prompt = load_task_prompt(task)
    clause = re.search(r"`kind`, ((?:`\w+`, )*`\w+` or `\w+`)", prompt)
    assert clause is not None

    assert _keys(clause.group(1)) == {kind.value for kind in GroupKind}
    assert "A `manifest` group" in prompt
    assert "uv run devops ci test" in prompt


@pytest.mark.parametrize("task", _PLAN_PROMPTS)
def test_the_prompt_names_the_value_of_a_criterion_that_only_a_person_delivers(task: str) -> None:
    assert f"`{PENDING_PERSON}`" in load_task_prompt(task)


# ── The limits ────────────────────────────────────────────────────────────────


def _prompt_limit(key: str) -> int:
    """The number in the sentence of the prompt that says `key` has at most N characters."""
    found = re.search(rf"- `{key}`:[^\n]*?at most (\d+) characters", _PROMPT)
    assert found is not None
    return int(found.group(1))


def test_the_summary_limit_of_the_prompt_is_the_limit_of_the_schema_and_fits_the_title() -> None:
    """The job writes `docs(spec): plan #<number> <summary>`; the part after the colon has
    at most `SUMMARY_MAX_CHARS` characters (CONTRIBUTING.md, Naming). The prompt names the one
    limit of the schema, which fits after the longest lead, so the job cuts no summary (#3249)."""
    limit = _prompt_limit("summary")
    summary = "a" * limit
    lead = staging_title(_LARGEST_NUMBER, "").split(": ", 1)[1]

    assert limit == stage_summary_limit() == SUMMARY_MAX_CHARS - len(lead)
    assert staging_title(_LARGEST_NUMBER, summary).endswith(summary)
    assert make_stage_proposal(summary=summary).summary == summary


def test_the_prompt_gives_the_form_of_the_title_that_the_job_writes() -> None:
    title = staging_title(_LARGEST_NUMBER, "summary")
    form = title.replace(str(_LARGEST_NUMBER), "<number>").replace("summary", "<summary>")

    assert f"`{form}`" in _PROMPT


def test_the_body_of_the_plan_fits_the_body_limit_of_the_contributing_guide() -> None:
    """The draft body is `Plans #<number>`, the body of the plan and the `Change:` line. With a body
    of the length that the prompt asks for, the longest number and a long slug, it stays within
    the limit of a body that CONTRIBUTING.md sets and that the delivery uses, so a body that keeps
    to the prompt needs no shorter text."""
    found = re.search(r"in at most ([\d,]+) characters before the trailers", _CONTRIBUTING)
    assert found is not None
    limit = int(found.group(1).replace(",", ""))
    text = "a" * _prompt_limit("pull_request_body")
    body = pull_request_body(_LARGEST_NUMBER, f"{_LARGEST_NUMBER}-{'a' * 60}", text)

    assert limit == CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS
    assert len(body) <= limit


def test_the_purpose_limit_of_the_prompt_is_the_one_of_the_check_and_of_the_config() -> None:
    prompt_count = re.search(r"`purpose` of at least (\d+) characters", _PROMPT)
    config_count = re.search(r"of at least (\d+) characters, so archive never writes TBD", _CONFIG)
    assert prompt_count is not None
    assert config_count is not None

    assert int(prompt_count.group(1)) == PURPOSE_MIN_CHARS == int(config_count.group(1))


# ── The paths of a group ──────────────────────────────────────────────────────


# ── The self-acceptance test of a plan rule (#3404) ──────────────────────────


# ── The spec delta ────────────────────────────────────────────────────────────


def _no_spec_prefixes() -> list[str]:
    """The paths that the prompt says need no spec delta."""
    sentence = re.search(r"when every path is under (.*?), the check refuses", _PROMPT, re.S)
    assert sentence is not None
    return _spans(sentence.group(1))


def _delta_plan(path: str) -> list[str]:
    """What `check_proposal` finds in a plan that changes `path` and carries a spec delta."""
    group = StageGroup.model_validate(
        {
            "title": "Change one file",
            "kind": "other",
            "changes": [path],
            "implementation": "Edit the file",
            "process": "Read the file",
        }
    )
    proposal = make_stage_proposal(groups=[group], skip_specs=False)
    return check_proposal(proposal, [], StagedTree([path, "src/devops_cli/sample.py"]), registry=())


def _refused_prefixes() -> list[str]:
    """The paths that the check names when it refuses a spec delta: it says them in its problem."""
    problems = _delta_plan("docs/sample.md")
    found = re.search(r"is under (.*?)\. These paths", " ".join(problems))
    assert found is not None
    return re.split(r", | or ", found.group(1))


def test_the_prompt_lists_the_paths_that_the_check_takes_for_unobserved() -> None:
    assert sorted(_no_spec_prefixes()) == sorted(_refused_prefixes())


@pytest.mark.parametrize("prefix", _refused_prefixes())
def test_the_check_refuses_a_spec_delta_for_each_path_that_it_names(
    prefix: str,
) -> None:
    assert any("spec delta" in problem for problem in _delta_plan(f"{prefix}sample.md"))


@pytest.mark.parametrize(
    "path",
    [
        "src/devops_cli/sample.py",
        "k8s/sample.yaml",
        "src/devops_cli/ai/tasks/sample.md",
    ],
)
def test_the_check_wants_a_spec_delta_for_a_path_outside_the_list(path: str) -> None:
    assert not any("spec delta" in problem for problem in _delta_plan(path))


def test_the_check_refuses_a_spec_delta_for_root_documents() -> None:
    group = StageGroup.model_validate(
        {
            "title": "Edit documents",
            "kind": "other",
            "changes": ["SECURITY.md", "CONTRIBUTING.md"],
            "implementation": "Edit root documents",
            "process": "Read the documents",
        }
    )
    proposal = make_stage_proposal(groups=[group], skip_specs=False)
    problems = check_proposal(
        proposal,
        [],
        StagedTree(["SECURITY.md", "CONTRIBUTING.md", "src/devops_cli/sample.py"]),
        registry=(),
    )
    assert any("These paths need no spec delta" in problem for problem in problems)


def test_the_check_refuses_a_spec_delta_for_knowledge_base_manual_and_tests() -> None:
    group = StageGroup.model_validate(
        {
            "title": "Edit manual and test",
            "kind": "other",
            "changes": [
                "src/devops_cli/ai/knowledge_base/example.md",
                "tests/roadmap/test_sample.py",
            ],
            "implementation": "Edit files",
            "process": "Read files",
        }
    )
    proposal = make_stage_proposal(groups=[group], skip_specs=False)
    problems = check_proposal(
        proposal,
        [],
        StagedTree(
            [
                "src/devops_cli/ai/knowledge_base/example.md",
                "tests/roadmap/test_sample.py",
                "src/devops_cli/sample.py",
            ]
        ),
        registry=(),
    )
    assert any("These paths need no spec delta" in problem for problem in problems)


def test_the_check_accepts_skip_specs_for_knowledge_base_manual_and_tests() -> None:
    group = StageGroup.model_validate(
        {
            "title": "Edit manual and test",
            "kind": "other",
            "changes": [
                "src/devops_cli/ai/knowledge_base/example.md",
                "tests/roadmap/test_sample.py",
            ],
            "implementation": "Edit files",
            "process": "Read files",
        }
    )
    proposal = make_stage_proposal(groups=[group], skip_specs=True, specs=[])
    problems = check_proposal(
        proposal,
        [],
        StagedTree(
            [
                "src/devops_cli/ai/knowledge_base/example.md",
                "tests/roadmap/test_sample.py",
                "src/devops_cli/sample.py",
            ]
        ),
        registry=(),
    )
    assert not any("spec delta" in problem for problem in problems)


def test_the_check_accepts_a_spec_delta_for_task_prompt_under_src() -> None:
    path = "src/devops_cli/ai/tasks/roadmap_stage_change.md"
    problems = _delta_plan(path)
    assert not any("These paths need no spec delta" in problem for problem in problems)


# ── The commands of `verify` ──────────────────────────────────────────────────


def _verify_forms() -> list[str]:
    """The commands that the prompt gives as a form of `verify`: the code spans that start with
    `uv run devops` or `! git grep`."""
    return [s for s in _spans(_PROMPT) if s.startswith(("uv run devops", "! git grep -n"))]


def _group(verify: str) -> StageGroup:
    return StageGroup.model_validate(
        {
            "title": "Check the documents",
            "kind": "other",
            "changes": ["docs/sample.md"],
            "implementation": "Edit the document",
            "verify": verify,
        }
    )


def test_the_prompt_gives_verify_forms() -> None:
    assert len(_verify_forms()) >= 5


@pytest.mark.parametrize("form", sorted(set(_verify_forms())))
def test_each_verify_form_of_the_prompt_passes_the_form_check(form: str) -> None:
    """The prompt writes the name of a search as the placeholder `<name>`. The gate refuses the
    placeholder as a literal (#3263), so the check gives it a name."""
    assert form_problems([_group(form.replace("<name>", "old_name"))]) == []


@pytest.mark.parametrize(
    "form", sorted(f for f in set(_verify_forms()) if f.startswith("uv run devops"))
)
def test_each_devops_command_of_the_prompt_is_a_command_of_devops(form: str) -> None:
    tokens = shlex.split(form)[3:]

    assert resolve_devops_argv(tokens) is None


# ── A move of a name prefix (#3372) ──────────────────────────────────────────


# ── A citation of a line or a symbol (#3422) ─────────────────────────────────


# ── The preconditions of a called function (#3309) ───────────────────────────


# ── The phrases that a document and the prompt keep together ──────────────────


# ── The living-spec rule (#3295) ─────────────────────────────────────────────


# ── A plan that a person rejected (#3503) ─────────────────────────────────────


# ── A command or an option that the issue removes or renames (#3287) ─────────


def test_the_stage_prompt_gives_the_removal_sentence_that_the_check_reads() -> None:
    """The check counts a name as removed only when MUST NOT governs it (#4954), so the prompt gives
    the planner one sentence for a removal, and the check reads the old name from that sentence."""
    (rule,) = re.findall(r"- When the issue removes or renames[^\n]*", _PROMPT)
    (sentence,) = re.findall(r'"(`<old name>` MUST NOT exist\.)"', rule)
    old = "devops roadmap intake-eval"
    scenario = {
        "name": "The old name",
        "when": "a person runs it",
        "then": "the CLI refuses it",
    }
    spec = {
        "capability": "roadmap-eval",
        "added": [
            {
                "name": "The old command is gone",
                "text": sentence.replace("<old name>", old),
                "scenarios": [scenario],
            }
        ],
        "modified": [],
    }

    problems = check_proposal(
        make_stage_proposal(specs=[spec]),
        ["roadmap-eval"],
        StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"]),
        registry=(),
        requirement_texts={"roadmap-eval": {"The old command runs": f"`{old}` SHALL run."}},
    )

    assert len(problems) == 1
    assert f"`{old}`" in problems[0]


# ── A requirement whose name no longer fits its text (#5340) ─────────────────


# ── A plan that changes a planner prompt (#3347) ──────────────────────────────


# ── Cite staged constant values (#3308) ───────────────────────────────────────


# ── Count of a claimed set (#3304) ────────────────────────────────────────────


def test_the_plan_check_refuses_no_word_of_a_requirement_text() -> None:
    proposal = make_stage_proposal()
    req = (
        proposal.specs[0]
        .added[0]
        .model_copy(update={"text": "Every caller SHALL pass a valid configuration."})
    )
    spec = proposal.specs[0].model_copy(update={"added": [req]})
    proposal_with_every = proposal.model_copy(update={"specs": [spec]})
    problems = check_proposal(
        proposal_with_every,
        known=[s.capability for s in proposal.specs],
        tree=StagedTree(proposal.groups[0].changes),
        registry=(),
    )
    assert not any("every" in p.lower() for p in problems)


# ── Refuse a self-named or untested plan (#3321) ──────────────────────────────


# ── References to a moved module (#3373) ─────────────────────────────────────


def _prompt_reason_when_changed() -> object:
    """The value that the `references` key of the prompt gives to `reason` when `unchanged` is
    false: the words after `else` in the sentence about `reason`."""
    bullet = re.search(r"^- `references`:.*$", _reply_section(_PROMPT), flags=re.MULTILINE)
    assert bullet is not None
    clause = re.search(r"`reason` is [^.]*?, else (null|an empty string)\.", bullet.group(0))
    assert clause is not None, "the references key states no value of `reason` when unchanged"
    return None if clause.group(1) == "null" else ""


def test_a_reply_that_follows_the_references_key_of_the_prompt_passes_the_schema() -> None:
    reply = {
        "path": "src/devops_cli/sample.py",
        "kind": "import",
        "unchanged": False,
        "reason": _prompt_reason_when_changed(),
    }

    plan = make_stage_proposal(references=[reply])

    assert [ref.path for ref in plan.references] == ["src/devops_cli/sample.py"]


# ── One exact change and failing test (#3433) ─────────────────────────────────


# ── Whole-suite criteria and no empty task groups (#4114) ────────────────────


# ── Rejected alternatives with a fact (#3257) ────────────────────────────────


# ── Unknown criteria entries refused (#3391) ─────────────────────────────────
