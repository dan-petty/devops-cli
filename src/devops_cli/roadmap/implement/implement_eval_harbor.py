"""The export of an implement fixture as a Harbor task (#3104).

Harbor (harbor-framework/harbor) runs one agent on one task in a container, N times, and reports
the reward of each trial. A task is a folder of four files: `instruction.md`, the environment
`Dockerfile`, the test script `tests/test.sh` and the configuration `task.toml`. This module renders
the four from a fixture of `devops roadmap eval implement` (`implement_eval`), so the trials of a
fixture run with another harness and compare with the numbers of another agent.

The four texts are the contract with the pinned Harbor version: a correction of that version
changes one function here and its test, and nothing else.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from devops_cli.config.constants import CONST_CANONICAL_OCI_SOURCE
from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.roadmap.implement.implement_eval import (
    ISSUE_FILE,
    PLAN_DIR,
    PLAN_FILES,
    LoadedCase,
    Property,
)

INSTRUCTION_FILE = "instruction.md"
ENVIRONMENT_DIR = "environment"
DOCKERFILE_NAME = "Dockerfile"
TESTS_DIR = "tests"
TEST_SCRIPT_NAME = "test.sh"
TASK_CONFIG_FILE = "task.toml"
# The file that the verifier of the pinned Harbor version reads the reward of a trial from, in the
# container of the task. The test script writes 1 or 0 there.
REWARD_FILE = "/logs/reward.txt"

# The limits of the container of a task. A check of the fixture runs the whole test suite of the
# repository, so the limits are those of the runner image.
_CPUS = 2
_MEMORY_MB = 4096
_STORAGE_MB = 10240
_SCRIPT_MODE = 0o755


def instruction_text(loaded: LoadedCase) -> str:
    """The instruction of the task: the title and the body of the issue of the fixture, and the
    three files of its plan."""
    case = loaded.case
    blocks = [
        f"# {case.title}",
        f"Issue #{case.issue}, group {case.group} of the plan, at commit `{case.base}`.",
        (
            f"Do the work of group {case.group} of the plan below, and tick each task of the "
            "group in `tasks.md` when it is done."
        ),
        f"## The issue\n\n{loaded.body.strip()}",
        "## The plan",
        *(f"### {name}\n\n{loaded.plan[name].strip()}" for name in PLAN_FILES),
    ]
    return "\n\n".join(blocks) + "\n"


def dockerfile_text(loaded: LoadedCase) -> str:
    """The environment of the task: this repository at the base commit of the fixture, with the
    interpreter, uv and the tools that the checks of the fixture use."""
    base = (
        importlib.resources.files("devops_cli.roadmap.implement.harbor")
        .joinpath("Dockerfile")
        .read_text(encoding="utf-8")
        .rstrip()
    )
    return (
        f"{base}\n\n"
        "WORKDIR /app\n"
        f"RUN git clone --quiet {CONST_CANONICAL_OCI_SOURCE} /app \\\n"
        f"    && git -C /app checkout --quiet --detach {loaded.case.base}\n"
        "\n"
        "RUN uv sync --frozen\n"
    )


def test_script_text(loaded: LoadedCase) -> str:
    """The test script of the task: it runs each command that names the tests of the fixture, and
    writes 1 as the reward when they all pass and 0 when one fails."""
    lines = [
        "#!/bin/bash",
        "# The reward of one trial: 1 when every check of the fixture passes, and 0 otherwise.",
        f"# The verifier of Harbor reads the reward from {REWARD_FILE}.",
        "set -u",
        "",
        "reward=1",
    ]
    for command in loaded.case.tests_pass:
        lines += [f"if ! {command}; then", "  reward=0", "fi"]
    lines += [
        "",
        f'mkdir -p "$(dirname {REWARD_FILE})"',
        f"""printf '%s\\n' "$reward" > {REWARD_FILE}""",
    ]
    return "\n".join(lines) + "\n"


def task_config_text(loaded: LoadedCase, timeout_seconds: int) -> str:
    """The configuration of the task: its name, the time limit of one trial and the limits of its
    container."""
    case = loaded.case
    limit = f"{timeout_seconds:.1f}"
    lines = [
        'version = "1.0"',
        "",
        "[metadata]",
        f'name = "{case.name}"',
        (
            f'description = "Issue #{case.issue}, group {case.group}, at {case.base[:12]}. '
            'The export of an implement eval fixture."'
        ),
        "",
        "[verifier]",
        f"timeout_sec = {limit}",
        "",
        "[agent]",
        f"timeout_sec = {limit}",
        "",
        "[environment]",
        f"build_timeout_sec = {limit}",
        f"cpus = {_CPUS}",
        f"memory_mb = {_MEMORY_MB}",
        f"storage_mb = {_STORAGE_MB}",
    ]
    return "\n".join(lines) + "\n"


def require_text(fixture: str, field: str, text: str) -> None:
    """Refuse the fixture when `text` holds no word, and name the fixture and the field (#3104)."""
    if not text.strip():
        raise ImplementEvalError(f"Fixture {fixture}: {field} holds no text.")


def export_task(loaded: LoadedCase, folder: Path, timeout_seconds: int) -> Path:
    """Write the four files of the task of `loaded` into `folder`, and return the folder. The test
    script is executable, so the verifier of Harbor can run it. A fixture that lacks the text of the
    issue, of a plan file or of a test command is refused before the first file is written."""
    _require_task_text(loaded)
    _write(folder / INSTRUCTION_FILE, instruction_text(loaded))
    _write(folder / ENVIRONMENT_DIR / DOCKERFILE_NAME, dockerfile_text(loaded))
    script = _write(folder / TESTS_DIR / TEST_SCRIPT_NAME, test_script_text(loaded))
    script.chmod(_SCRIPT_MODE)
    _write(folder / TASK_CONFIG_FILE, task_config_text(loaded, timeout_seconds))
    return folder


def _require_task_text(loaded: LoadedCase) -> None:
    """Refuse the fixture when the issue body, a plan file or a test command holds no word."""
    require_text(loaded.name, ISSUE_FILE, loaded.body)
    for file in PLAN_FILES:
        require_text(loaded.name, f"{PLAN_DIR}/{file}", loaded.plan[file])
    for command in loaded.case.tests_pass:
        require_text(loaded.name, Property.NAMED_TESTS, command)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
