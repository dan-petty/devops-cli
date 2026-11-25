"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
)
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from tests.support.markdown_examples import CodeSnippet, devops_commands

WORKFLOWS_DIR = Path(".github/workflows")
RELEASE_PATH = WORKFLOWS_DIR / "release.yml"
RELEASE_IMAGE_PATH = WORKFLOWS_DIR / "release-image.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a GitHub Actions workflow YAML file."""
    assert path.is_file(), f"Workflow file not found: {path}"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict), f"Workflow {path} does not parse as a mapping"
    return {"on" if k is True else str(k): v for k, v in content.items()}


def test_every_job_has_a_limit_and_each_step_limit_is_under_it() -> None:
    """With no `timeout-minutes`, a job runs for 360 minutes. A step limit that is not under the
    limit of its job never fires, because the job limit cancels the job first (#4677)."""
    problems = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for job_id, job in _load_workflow(path)["jobs"].items():
            if "uses" in job:
                continue
            limit = job.get("timeout-minutes")
            if not isinstance(limit, int):
                problems.append(f"{path.name}:{job_id} has no timeout-minutes")
                continue
            problems.extend(
                f"{path.name}:{job_id}:{step.get('name')} step limit {step['timeout-minutes']}"
                f" is not under the job limit {limit}"
                for step in job.get("steps", [])
                if "timeout-minutes" in step and not step["timeout-minutes"] < limit
            )

    assert problems == []


def _extract_steps_with_action(
    workflow: dict[str, Any], action_prefix: str
) -> list[tuple[str, dict[str, Any]]]:
    """Extract (job_id, step) pairs where the step uses an action matching action_prefix."""
    steps_found: list[tuple[str, dict[str, Any]]] = []
    for job_id, job in workflow.get("jobs", {}).items():
        if isinstance(job, dict):
            for step in job.get("steps", []):
                if isinstance(step, dict) and action_prefix in str(step.get("uses", "")):
                    steps_found.append((str(job_id), step))
    return steps_found


def _assert_attest_build_provenance_contract(workflow: dict[str, Any]) -> None:
    """Assert that actions/attest and actions/attest-build-provenance steps specify subject-name
    when subject-digest is present."""
    attest_steps = _extract_steps_with_action(workflow, "actions/attest")
    assert attest_steps, "Expected at least one actions/attest step in workflow"
    for job_id, step in attest_steps:
        with_args = step.get("with", {})
        assert isinstance(with_args, dict), f"Step 'with' must be a dict in job '{job_id}'"
        has_digest = "subject-digest" in with_args
        has_name = bool(with_args.get("subject-name"))
        assert not has_digest or has_name, (
            f"attest-build-provenance in job '{job_id}' has subject-digest without subject-name"
        )


_RELEASE_CREATED = "needs.release-please.outputs.release_created == 'true'"


def _needs(job: dict[str, Any]) -> list[str]:
    """The jobs a job needs, as a list."""
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _gated(jobs: dict[str, Any], name: str) -> bool:
    """Whether a job runs only when release-please created a release: it carries the gate
    itself, or it has no condition of its own and needs a gated job, since a skipped need skips
    it."""
    job = jobs[name]
    if "if" in job:
        return job["if"] == _RELEASE_CREATED
    return any(name != "release-please" and _gated(jobs, need) for need in _needs(job))


def test_release_workflow_attest_build_provenance_contract() -> None:
    """Validate that the release workflows specify subject-name for each attestation of a digest."""
    workflows = (_load_workflow(RELEASE_PATH), _load_workflow(RELEASE_IMAGE_PATH))
    for workflow in workflows:
        _assert_attest_build_provenance_contract(workflow)


def test_release_workflow_attest_build_provenance_mutation() -> None:
    """Validate that omitting subject-name from attest-build-provenance raises an AssertionError."""
    import copy

    workflow = _load_workflow(RELEASE_PATH)
    mutated = copy.deepcopy(workflow)
    for _job_id, step in _extract_steps_with_action(mutated, "actions/attest-build-provenance"):
        step.get("with", {}).pop("subject-name", None)

    with pytest.raises(AssertionError, match="has subject-digest without subject-name"):
        _assert_attest_build_provenance_contract(mutated)


# ── Every `devops` command the automation runs (#861) ─────────────────────────

GITHUB_DIR = Path(".github")
PRE_COMMIT_PATH = Path(".pre-commit-config.yaml")


def _automation_files() -> list[Path]:
    """Every workflow and composite action."""
    return sorted([*WORKFLOWS_DIR.glob("*.y*ml"), *(GITHUB_DIR / "actions").glob("*/action.y*ml")])


def _run_blocks(node: Any) -> Iterator[str]:
    """Every `run:` script under `node`: workflow job steps and composite action steps alike."""
    if isinstance(node, dict):
        if isinstance(node.get("run"), str):
            yield node["run"]
        for value in node.values():
            yield from _run_blocks(value)
    elif isinstance(node, list):
        for value in node:
            yield from _run_blocks(value)


def _extract_devops_commands(document: Any) -> list[list[ArgvToken]]:
    """The words after `devops` in each command the document's `run:` scripts run, read as a
    shell reads them: a variable or command substitution is a placeholder."""
    return [
        tokens
        for script in _run_blocks(document)
        for _, tokens in devops_commands(CodeSnippet(1, script, fenced=True))
    ]


def _pre_commit_commands() -> list[list[ArgvToken]]:
    """Each pre-commit hook's `devops` command: its entry, its `args`, then the staged files
    pre-commit passes unless `pass_filenames` is false."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo.get("hooks", [])]
    return [
        [
            *tokens,
            *hook.get("args", []),
            *(
                [ArgvPlaceholder(expression="staged files")]
                if hook.get("pass_filenames", True)
                else []
            ),
        ]
        for hook in hooks
        for _, tokens in devops_commands(CodeSnippet(1, str(hook.get("entry", "")), fenced=True))
    ]


def test_every_devops_command_the_workflows_actions_and_hooks_run_resolves() -> None:
    """A renamed or removed command or option breaks the workflow that runs it only when that
    workflow next runs; this finds it against the command tree first."""
    workflow_commands = [
        tokens
        for path in _automation_files()
        for tokens in _extract_devops_commands(_load_workflow(path))
    ]
    hook_commands = _pre_commit_commands()
    unresolved = [
        (" ".join(map(str, tokens)), finding.describe())
        for tokens in [*workflow_commands, *hook_commands]
        if (finding := resolve_devops_argv(tokens)) is not None
    ]
    assert (bool(workflow_commands), bool(hook_commands), unresolved) == (True, True, [])


def _pre_push_hooks() -> list[dict[str, Any]]:
    """The hooks of the `pre-push` stage of `.pre-commit-config.yaml`, in file order."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    default_stages = config.get("default_stages", ["pre-commit"])
    return [
        hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if "pre-push" in hook.get("stages", default_stages)
    ]


def _argv(hook: dict[str, Any]) -> list[str]:
    return [*shlex.split(str(hook.get("entry", ""))), *map(str, hook.get("args", []))]


# The default limit of the shell tool of an agent, which runs `git push` and so the pre-push
# hooks, and the time that a push takes outside the hook limits: the start of pre-commit, the
# transfer to GitHub, and the stop of the rows of two `devops ci` hooks after their limits, each
# at most SIGINT, SIGTERM and the reap with 3 s each. An inner limit ends before the limit around
# it (#4775).
AGENT_SHELL_LIMIT_SECONDS = 120
PUSH_OUTSIDE_HOOKS_SECONDS = 25
TIMEOUT_LIMIT = re.compile(r"\btimeout (\d+) ")


def _pre_push_overrun(hooks: list[dict[str, Any]]) -> list[str]:
    """The id of each hook that runs with no coreutils `timeout` limit, and the total time when
    the limits and the rest of the push do not end before the agent shell limit."""
    limits = {
        hook["id"]: [int(seconds) for seconds in TIMEOUT_LIMIT.findall(shlex.join(_argv(hook)))]
        for hook in hooks
    }
    total = sum(map(sum, limits.values())) + PUSH_OUTSIDE_HOOKS_SECONDS
    unbounded = [hook_id for hook_id, found in limits.items() if not found]
    return unbounded + ([f"{total} s"] if total >= AGENT_SHELL_LIMIT_SECONDS else [])


def test_the_pre_push_hooks_end_before_the_agent_shell_limit() -> None:
    """Each pre-push hook runs under coreutils `timeout`, and the limits and the rest of the push
    add up to less than the 120 s default limit of the agent shell. So a hook at its limit fails
    with its name, and `devops ci` stops its rows, before the shell ends the push (#4775)."""
    assert _pre_push_overrun(_pre_push_hooks()) == []


def test_a_pre_push_sum_past_the_shell_limit_or_a_hook_with_no_limit_is_refused() -> None:
    """The negative control: a total of 121 s and a hook with no limit are refused, and a total
    of 119 s passes."""

    def hooks(*entries: str) -> list[dict[str, Any]]:
        return [{"id": f"h{index}", "entry": entry} for index, entry in enumerate(entries)]

    hook_seconds = 121 - PUSH_OUTSIDE_HOOKS_SECONDS
    assert (
        _pre_push_overrun(hooks(f"timeout {hook_seconds - 6} sh -c true", "timeout 6 true")),
        _pre_push_overrun(hooks(f"timeout {hook_seconds - 2} true")),
        _pre_push_overrun(hooks("timeout 20 true", "uv run devops ci --check --only format")),
    ) == (["121 s"], [], ["h1"])


def test_a_misspelled_command_in_a_workflow_is_reported() -> None:
    """The negative control: extraction and resolution together report a command that does not
    exist, inside a command substitution and a compound line."""
    workflow = {
        "jobs": {
            "job": {
                "steps": [
                    {"run": 'OUT=$(uv run devops gh milestones clsoe "$NAME") || true'},
                    {"run": 'uv run devops gh milestones status \\\n  "$NAME"'},
                ]
            }
        }
    }
    found = [resolve_devops_argv(tokens) for tokens in _extract_devops_commands(workflow)]
    assert [None if f is None else f.token for f in found] == ["clsoe", None]


def test_no_run_block_interpolates_an_actions_expression() -> None:
    """Actions pastes a `${{ }}` expression into the script before the shell parses it, so a
    value holding `$(...)` runs; each value reaches `run:` through the step's `env:` (#861)."""
    interpolating = [
        str(path)
        for path in _automation_files()
        for script in _run_blocks(_load_workflow(path))
        if "${{" in script
    ]
    assert interpolating == []


def _uses(node: Any) -> Iterator[str]:
    """Every `uses:` reference under `node`: steps, composite action steps and reusable workflows."""
    if isinstance(node, dict):
        if isinstance(node.get("uses"), str):
            yield node["uses"]
        for value in node.values():
            yield from _uses(value)
    elif isinstance(node, list):
        for value in node:
            yield from _uses(value)


def test_every_remote_action_is_pinned_to_a_commit_sha() -> None:
    """A tag or branch can be moved to other code; a 40-character commit SHA cannot. Local
    `./` actions are this repository's own. `docker://` images are pinned by digest (#1119)."""
    unpinned = [
        f"{path}: {ref}"
        for path in _automation_files()
        for ref in _uses(_load_workflow(path))
        if not ref.startswith("./")
        and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", ref)
        and not (ref.startswith("docker://") and re.search(r"@sha256:[0-9a-f]{64}", ref))
    ]
    assert unpinned == []


def test_every_checkout_states_its_credentials_and_only_a_pushing_job_keeps_them() -> None:
    """actions/checkout leaves the job's token in `.git/config` unless told not to, where any later
    step, or an uploaded artifact, can read it (zizmor's artipacked). Only a job that runs
    `git push` keeps it."""
    checkouts = []
    for path in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        for job_id, job in _load_workflow(path).get("jobs", {}).items():
            steps = job.get("steps", [])
            pushes = any(re.search(r"\bgit\s+push\b", str(s.get("run", ""))) for s in steps)
            checkouts += [
                (f"{path.name}:{job_id}", step.get("with", {}).get("persist-credentials"), pushes)
                for step in steps
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
    assert [(where, kept) for where, kept, pushes in checkouts if kept is not pushes] == []


def test_sdlc_names_only_the_supply_chain_controls_the_repository_runs() -> None:
    """SDLC.md once claimed weekly Dependabot audits, pip-audit and SLSA Level 3, none of which
    the repository had; the audit and the workflow gate it names are the checks `devops ci`
    runs."""
    sdlc = Path("docs/SDLC.md").read_text(encoding="utf-8")
    assert (
        [claim for claim in ("Dependabot", "pip-audit", "SLSA Level 3") if claim in sdlc],
        get_check_spec("audit").cmd,
        "zizmor" in sdlc,
    ) == ([], ["uv", "audit"], True)


# ── The OpenSpec gate's workflows (#1844) ─────────────────────────────────────


# ── The design tokens job (#5184) ─────────────────────────────────────────────


# ── The plan-only pull request (#2860) ────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "is_plan_file"),
    [
        ("openspec/changes/2860-plan-only/proposal.md", True),
        ("openspec/changes/2860-plan-only/specs/ci/spec.md", True),
        ("openspec/changes/2860-plan-only/.openspec.yaml", True),
        ("openspec/changes/2860-plan-only/a/b/c.md", True),
        ("openspec/changes/2026-10-31-plan-only/proposal.md", True),
        ("openspec/changes/archive/2026-10-31-2860-plan-only/proposal.md", False),
        ("openspec/changes/archive/notes.md", False),
        ("openspec/changes/README.md", False),
        ("openspec/changes/.gitkeep", False),
        ("openspec/changes/2860-plan-only", False),
        ("openspec/changes/2860/proposal.md", False),
        ("openspec/changes/plan-only/proposal.md", False),
        ("openspec/specs/ci-job-time/spec.md", False),
        ("openspec/config.yaml", False),
        (".github/workflows/ci.yml", False),
        ("src/devops_cli/commands/ci.py", False),
        ("tests/invariants/test_change_folders.py", False),
        ("docs/SDLC.md", False),
        ("README.md", False),
        ("pyproject.toml", False),
    ],
)
def test_only_a_file_of_an_active_change_folder_counts_as_plan_only(
    path: str, is_plan_file: bool
) -> None:
    """`CONST_OPENSPEC_CHANGE_FOLDER_RE` matches a file only when it lies in an active change
    folder, `openspec/changes/<issue>-<slug>/<file>`. The archive, the living specs, the OpenSpec
    config, the workflows, `docs/`, the README, source and tests do not match (#2860)."""
    assert (re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, path) is not None) == is_plan_file


# ── The plan check of a Service plan pull request (#3103) ─────────────────────

_EQUALS_TERM = re.compile(r"(?P<path>[\w.]+) == '(?P<value>[^']*)'")
_STARTS_WITH_TERM = re.compile(r"startsWith\((?P<path>[\w.]+), '(?P<prefix>[^']*)'\)")


def _eval_term(term: str, event: dict[str, str]) -> bool:
    cleaned = term.strip()
    if cleaned.startswith("(") and cleaned.endswith(")") and "||" in cleaned:
        return any(_eval_term(part, event) for part in cleaned[1:-1].split("||"))
    equals, starts = _EQUALS_TERM.fullmatch(cleaned), _STARTS_WITH_TERM.fullmatch(cleaned)
    if cleaned in {"always()", "!cancelled()"}:
        return True
    if equals is not None:
        return event[equals["path"]].lower() == equals["value"].lower()
    if starts is not None:
        return event[starts["path"]].lower().startswith(starts["prefix"].lower())
    raise AssertionError(f"the condition holds a term the test cannot read: {term}")
