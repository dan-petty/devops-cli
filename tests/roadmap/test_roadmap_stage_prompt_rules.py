"""`devops roadmap stage`: the prompts of the planner agree with the rules they restate (#3202).

The planner gets no `AGENTS.md`, `CONTRIBUTING.md` or `docs/TESTING.md`, so its prompt is the only
copy of a rule that it reads. A rule that has a machine form (a limit, a key, a form of a command, a
list of paths) is read here from that form, and the prompt must say the same. A rule that has no
machine form is held by a phrase that the prompt and the document must both keep: when one side
changes the phrase, the test sends the author to the other side.
"""

from __future__ import annotations

import re
import shlex

import pytest
from pydantic import BaseModel

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS
from devops_cli.core.command_resolver import resolve_devops_argv
from devops_cli.roadmap.stage_change import (
    BODY_MAX_CHARS,
    CREATED_LINE_TOKENS,
    PURPOSE_MIN_CHARS,
    SUMMARY_MAX_CHARS,
    GroupKind,
    StageDecision,
    StageGroup,
    StageProposal,
    StageRejection,
    StageRequirement,
    StageScenario,
    StageSpec,
    check_proposal,
    closing_keyword_in,
    pull_request_body,
    staging_title,
)
from devops_cli.roadmap.stage_criteria import PENDING_PERSON, StageCriterion
from devops_cli.roadmap.stage_form import form_problems
from devops_cli.roadmap.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal, stage_summary_limit
from tests.support.paths import REPO_ROOT

_CHANGE_PROMPT = "roadmap_stage_change.md"
_SPLIT_PROMPT = "roadmap_stage_split.md"
_PROMPT = load_task_prompt(_CHANGE_PROMPT)
_CONTRIBUTING = (REPO_ROOT / "CONTRIBUTING.md").read_text("utf-8")
_TESTING = (REPO_ROOT / "docs" / "TESTING.md").read_text("utf-8")
_CONFIG = (REPO_ROOT / "openspec" / "config.yaml").read_text("utf-8")
_AGENTS = (REPO_ROOT / "AGENTS.md").read_text("utf-8")
_DOCUMENTS = {
    "AGENTS.md": _AGENTS,
    "CONTRIBUTING.md": _CONTRIBUTING,
    "docs/TESTING.md": _TESTING,
    "openspec/config.yaml": _CONFIG,
}
# The largest issue number that the title has to hold with its lead.
_LARGEST_NUMBER = 999999
_CODE_SPAN = re.compile(r"`([^`]+)`")
# The keys that a sentence lists: `a`, `b` and `c`.
_KEY_LIST = re.compile(r"((?:`\w+`(?:, | and |, and )?)+)")
# The words that GitHub reads as closing keywords (docs.github.com, "Linking a pull request to an
# issue"). A pull request that only plans an item must hold none before an issue reference.
_GITHUB_CLOSING_KEYWORDS = (
    "close",
    "closes",
    "closed",
    "fix",
    "fixes",
    "fixed",
    "resolve",
    "resolves",
    "resolved",
)


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
    ],
)
def test_each_list_of_keys_of_the_reply_is_the_fields_of_a_model(model: type[BaseModel]) -> None:
    lists = [_keys(found) for found in _KEY_LIST.findall(_reply_section(_PROMPT)) if found]
    expected = set(model.model_fields)

    assert expected in lists


@pytest.mark.parametrize("task", [_CHANGE_PROMPT, _SPLIT_PROMPT])
def test_the_keys_of_a_group_in_the_prompts_are_the_fields_of_a_group(task: str) -> None:
    prompt = load_task_prompt(task)
    clause = re.search(r"(?:has|with) these keys:(.*?)\. (?:Every task|A `behavior`)", prompt, re.S)
    assert clause is not None
    keys = [segment.split("`")[1] for segment in clause.group(1).split(";")]

    assert sorted(keys) == sorted(StageGroup.model_fields)


@pytest.mark.parametrize("task", [_CHANGE_PROMPT, _SPLIT_PROMPT])
def test_the_prompts_state_the_budget_and_the_line_estimate_rule(task: str) -> None:
    prompt = load_task_prompt(task)

    assert "`creates_lines`" in prompt
    assert f"{CREATED_LINE_TOKENS} tokens for each estimated line" in prompt
    assert "`creates` with no estimate is refused" in prompt
    assert "`budget`" in prompt


@pytest.mark.parametrize("task", [_CHANGE_PROMPT, _SPLIT_PROMPT])
def test_the_prompts_name_the_kinds_of_a_group_as_the_enum_does(task: str) -> None:
    prompt = load_task_prompt(task)
    clause = re.search(r"`kind`, `(\w+)` or `(\w+)`", prompt)
    assert clause is not None

    assert set(clause.groups()) == {kind.value for kind in GroupKind}


def test_the_prompt_names_the_value_of_a_criterion_that_only_a_person_delivers() -> None:
    assert f"`{PENDING_PERSON}`" in _PROMPT


def test_the_split_prompt_says_what_a_group_with_text_means() -> None:
    prompt = load_task_prompt(_SPLIT_PROMPT)
    assert (
        "A group with `text` has the markdown text of the group from `tasks.md` in place of the "
        "fields of a staged group."
    ) in prompt


# ── The limits ────────────────────────────────────────────────────────────────


def test_the_stage_prompt_states_the_documentation_verb_rule() -> None:
    assert "`documentation`, one text that starts with an imperative verb" in _PROMPT
    assert "names each document in a code span" in _PROMPT
    assert "or `null` when the step changes no document" in _PROMPT


def _prompt_limit(key: str) -> int:
    """The number in the sentence of the prompt that says `key` has at most N characters."""
    found = re.search(rf"- `{key}`:[^\n]*?at most (\d+) characters", _PROMPT)
    assert found is not None
    return int(found.group(1))


def test_the_summary_limit_of_the_prompt_is_the_limit_of_the_schema_and_fits_the_title() -> None:
    """The job writes `docs(openspec): plan #<number> <summary>`; the part after the colon has
    at most `SUMMARY_MAX_CHARS` characters (CONTRIBUTING.md, Naming). The prompt names the one
    limit of the schema, which fits after the longest lead, so the job cuts no summary (#3249)."""
    limit = _prompt_limit("summary")
    summary = "a" * limit
    lead = staging_title(_LARGEST_NUMBER, "").split(": ", 1)[1]

    assert limit == stage_summary_limit() == SUMMARY_MAX_CHARS - len(lead)
    assert staging_title(_LARGEST_NUMBER, summary).endswith(summary)
    assert make_stage_proposal(summary=summary).summary == summary


def test_the_prompt_says_that_the_limit_counts_the_summary_as_the_title_shows_it() -> None:
    """A handle or a link gets a code span in the title, and an emoji has two units for the check
    `Semantic PR title`, so the model writes none of them near the limit (#3249). Each claim is
    pinned, so a change of the sentence fails here."""
    (bullet,) = re.findall(r"- `summary`:[^\n]*", _PROMPT)

    assert "The limit counts the summary as the title shows it." in bullet
    assert "which adds characters, so write no handle or link in the summary." in bullet
    assert "An emoji counts as two characters." in bullet


def test_the_summary_limit_of_the_code_is_the_one_of_the_contributing_guide() -> None:
    found = re.search(r"summary[^.]*?has at most (\d+) characters", _CONTRIBUTING)
    assert found is not None

    assert SUMMARY_MAX_CHARS == int(found.group(1))


def test_the_prompt_gives_the_form_of_the_title_that_the_job_writes() -> None:
    title = staging_title(_LARGEST_NUMBER, "summary")
    form = title.replace(str(_LARGEST_NUMBER), "<number>").replace("summary", "<summary>")

    assert f"`{form}`" in _PROMPT


def test_the_body_limit_of_the_prompt_is_the_limit_of_the_schema() -> None:
    limit = _prompt_limit("pull_request_body")

    assert limit == BODY_MAX_CHARS
    assert make_stage_proposal(pull_request_body="a" * limit)
    with pytest.raises(ValueError, match="at most 800 characters"):
        make_stage_proposal(pull_request_body="a" * (limit + 1))


def test_the_body_of_the_plan_fits_the_body_limit_of_the_contributing_guide() -> None:
    """The draft body is `Plans #<number>`, the body of the plan and the `Change:` line. With the
    longest body, a five-digit number and a long slug, it stays within the limit of a body that
    CONTRIBUTING.md sets and that the delivery uses."""
    found = re.search(r"in at most ([\d,]+) characters before the trailers", _CONTRIBUTING)
    assert found is not None
    limit = int(found.group(1).replace(",", ""))
    proposal = make_stage_proposal(pull_request_body="a" * BODY_MAX_CHARS)
    body = pull_request_body(_LARGEST_NUMBER, f"{_LARGEST_NUMBER}-{'a' * 60}", proposal)

    assert limit == CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS
    assert len(body) <= limit


def test_the_purpose_limit_of_the_prompt_is_the_one_of_the_check_and_of_the_config() -> None:
    prompt_count = re.search(r"`purpose` of at least (\d+) characters", _PROMPT)
    config_count = re.search(r"of at least (\d+) characters, so archive never writes TBD", _CONFIG)
    assert prompt_count is not None
    assert config_count is not None

    assert int(prompt_count.group(1)) == PURPOSE_MIN_CHARS == int(config_count.group(1))


@pytest.mark.parametrize("keyword", _GITHUB_CLOSING_KEYWORDS)
def test_the_prompt_forbids_each_word_that_closes_an_issue(keyword: str) -> None:
    assert closing_keyword_in(f"{keyword} #12") == keyword
    assert re.search(rf"\b{keyword}\b", _PROMPT.split("Never write", 1)[1].split(".", 1)[0])


# ── The paths of a group ──────────────────────────────────────────────────────


def test_the_prompt_forbids_a_group_writing_a_change_folder_path() -> None:
    """A group must not change or create the change folder or a path under it (#3285): the job
    writes the change folder before the groups run, and a group reads the change it implements."""
    assert "must not change or create `openspec/changes`" in _PROMPT
    assert "refuses a `changes` or `creates` path" in _PROMPT


# ── The self-acceptance test of a plan rule (#3404) ──────────────────────────


def test_the_prompt_states_the_self_acceptance_rule_of_a_plan() -> None:
    """A plan that adds a rule of the plan check gives the test that accepts its own plan (#3404).
    The rule does not exist when the stage job reads the plan, so the plan gives the test itself,
    and the implement step runs it."""
    prompt = load_task_prompt(_CHANGE_PROMPT)

    assert "`StageProposal`" in prompt
    assert "`content_problems`" in prompt
    assert "A `behavior` group that changes `src/devops_cli/roadmap/stage_change.py`" in prompt
    assert "builds the plan's own `StageProposal`" in prompt
    assert "asserts that `content_problems` returns no problem" in prompt


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
    return check_proposal(proposal, [], StagedTree([path, "src/devops_cli/sample.py"]))


def _refused_prefixes() -> list[str]:
    """The paths that the check names when it refuses a spec delta: it says them in its problem."""
    problems = _delta_plan("docs/sample.md")
    found = re.search(r"is under (.*?)\. These paths", " ".join(problems))
    assert found is not None
    return re.split(r", | or ", found.group(1))


def test_the_prompt_lists_the_paths_that_the_check_takes_for_unobserved() -> None:
    assert sorted(_no_spec_prefixes()) == sorted(_refused_prefixes())


@pytest.mark.parametrize("prefix", _refused_prefixes())
def test_the_check_refuses_a_spec_delta_for_each_path_that_it_names(prefix: str) -> None:
    assert any("spec delta" in problem for problem in _delta_plan(f"{prefix}sample.md"))


@pytest.mark.parametrize("path", ["src/devops_cli/sample.py", "k8s/sample.yaml", "README.md"])
def test_the_check_wants_a_spec_delta_for_a_path_outside_the_list(path: str) -> None:
    assert not any("spec delta" in problem for problem in _delta_plan(path))


# ── The commands of `verify` ──────────────────────────────────────────────────


def _verify_forms() -> list[str]:
    """The commands that the prompt gives as a form of `verify`: the code spans that start with
    `uv run devops` or `! git grep`."""
    return [s for s in _spans(_PROMPT) if s.startswith(("uv run devops", "! git grep -n"))]


def _command(span: str) -> str:
    """The command of `span` as a document names it: with no `uv run` and no path to a test, such
    as `devops ci test`. A `! git grep` check is kept whole."""
    if span.startswith("! git grep"):
        return span
    words = span.removeprefix("uv run ").split()
    return " ".join(word for word in words if not word.startswith("tests/"))


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


def test_the_prompt_says_that_a_pytest_command_is_refused_and_the_check_refuses_it() -> None:
    assert "`uv run pytest` is refused" in _PROMPT
    assert form_problems([_group("uv run pytest tests/roadmap/test_stage.py")])


@pytest.mark.parametrize("form", sorted(set(_verify_forms())))
def test_the_testing_guide_holds_each_verify_form_of_the_prompt(form: str) -> None:
    assert _command(form) in _TESTING


def test_the_prompt_holds_each_verify_form_that_the_config_gives() -> None:
    kinds = _CONFIG.split("Give each group a kind.", 1)[1].split("- >-", 1)[0]
    config_forms = {_command(s) for s in _spans(kinds) if s.startswith(("uv run devops", "! git"))}
    prompt_forms = {_command(form) for form in _verify_forms()}

    assert len(config_forms) == 4
    assert config_forms <= prompt_forms


# ── A move of a name prefix (#3372) ──────────────────────────────────────────


def test_the_prompt_asks_for_every_module_of_a_moved_prefix() -> None:
    assert "lists every module of that prefix in `changes`" in _PROMPT
    assert "not the entry module only" in _PROMPT
    assert "never one sampled module" in _PROMPT


def test_the_prompt_asks_for_the_hit_count_of_a_negative_search() -> None:
    assert "call `search_code` with its literal on the staged commit" in _PROMPT
    assert "quote the hit count in `feasibility`" in _PROMPT
    assert "is no check" in _PROMPT
    assert "can never pass after it" in _PROMPT


# ── The phrases that a document and the prompt keep together ──────────────────

_SHARED = [
    ("AGENTS.md", "example.com"),
    ("AGENTS.md", "RFC 5737"),
    ("AGENTS.md", "<storage-node>"),
    ("AGENTS.md", "build, keep and fix it"),
    ("openspec/config.yaml", "example.com"),
    ("openspec/config.yaml", "RFC 5737"),
    ("openspec/config.yaml", "<storage-node>"),
    ("openspec/config.yaml", "double only process edges"),
    (
        "openspec/config.yaml",
        "`! git grep -n <name> src/ tests/` (a command that exits 0 when it finds nothing)",
    ),
    (
        "docs/TESTING.md",
        "`! git grep -n <name> src/ tests/` (a command that exits 0 when it finds nothing)",
    ),
    (
        "docs/TESTING.md",
        "a document, a manifest, a workflow, a deletion or a refactor that keeps behavior, "
        "an edit of tests only, or data",
    ),
    ("docs/TESTING.md", "mirrors the package"),
]


@pytest.mark.parametrize(("document", "phrase"), _SHARED)
def test_the_prompt_and_the_document_keep_the_same_phrase_of_a_rule(
    document: str, phrase: str
) -> None:
    assert phrase in _DOCUMENTS[document], f"{document} no longer says: {phrase}"
    assert phrase in _PROMPT, f"the prompt no longer says: {phrase}"


# ── The living-spec rule (#3295) ─────────────────────────────────────────────


def test_the_prompt_states_the_living_spec_rule() -> None:
    assert "A task group must not change or create a file under `openspec/specs/`" in _PROMPT
    assert "`openspec archive` writes the living specs" in _PROMPT


def test_the_prompt_states_the_dependencies_rule() -> None:
    assert "`dependencies`" in _PROMPT
    assert "`overlaps`" in _PROMPT
    assert "empty list" in _PROMPT


def test_the_prompt_names_a_sample_file_by_a_bare_name() -> None:
    assert "gets a bare name with no folder, such as `test_sample.py`" in _PROMPT
    assert "the check reads a name with a folder as a path of the repository" in _PROMPT


# ── A plan that a person rejected (#3503) ─────────────────────────────────────


@pytest.mark.parametrize(
    "task",
    ["roadmap_stage_change.md", "roadmap_refine_proposal.md", "roadmap_refine_investigation.md"],
)
def test_the_prompts_name_the_key_that_holds_the_reason_of_a_rejected_plan(task: str) -> None:
    prompt = load_task_prompt(task)

    assert ("rejected_plan" if task == "roadmap_stage_change.md" else "stage_return") in prompt
    assert "rejected" in prompt


def test_the_stage_prompt_says_the_plan_must_not_state_the_false_premise_again() -> None:
    prompt = load_task_prompt("roadmap_stage_change.md")

    assert "Do not plan again the premise that the reason shows to be false." in prompt
