"""File the issue drafts of the agent audit through `devops roadmap intake` (#2346).

A finding is one recurring problem of the agent sessions, and the model stage groups the findings
that share one cause (`grouping.py`). A group is one candidate issue, and this module files it:
intake is the one way that new work becomes an item of this repository, so the audit hands each
draft to `devops roadmap intake --title <title> --body-file <file> --confirm` rather than writing
an issue itself. Intake keeps its duplicate check, its labels and its placement, and the audit
writes no GitHub state.

The child is a `devops` command of the interpreter that runs the audit (`python -P -m
devops_cli.entry`, as `devops telemetry profile` starts a profiled command), so it reads the
settings, the GitHub session and the model of this checkout. It runs through the process runner
seam with a bound, so a child that hangs ends the audit with an error rather than holding it. The
body goes to a file of a temporary directory that the child reads and that the audit removes when
it ends, so no command line and no output of the child quotes a body.

The audit stops at the first draft that intake does not file: a run that went on would file the
other drafts on a roadmap that the failed run left part-written. That draft raises
`AgentAuditFilingError`, which names the title, the exit status of the child and the last line that
it printed.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from devops_cli.ai.agent_audit.grouping import FindingGroup, draft_body
from devops_cli.ai.agent_audit.transcript import sanitize_text
from devops_cli.config.constants import CONST_DEVOPS_CLI_ENTRY_MODULE
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import AgentAuditFilingError
from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length

# A callable that starts one child process, as `run_subprocess` does: the edge that a test fakes.
IntakeRunner = Callable[..., subprocess.CompletedProcess[str]]

# The lead of the title of a filed draft: a defect of an agent session, in the scope `ai` that
# `.github/labels.yml` declares. Intake refuses a summary over `SUMMARY_MAX_CHARS`, so a longer
# group name gives a shorter summary (`_summary`).
_TITLE_LEAD = "fix(ai): "
# The summary of a title whose group name holds no word that fits the limit.
_FALLBACK_SUMMARY = "a recurring problem of the agent sessions"
# The most characters of the output of the child that the error keeps (AGENTS.md rule 13).
_DETAIL_MAX_CHARS = 400
# The line that intake prints for each issue that it filed (`MESSAGES.roadmap.intake_filed`).
_FILED_LINE = re.compile(r"Filed #(?P<number>[0-9]+)")
# The text that the error names when the child printed nothing.
_NO_OUTPUT = "no output"


@dataclass(frozen=True, slots=True)
class Draft:
    """One issue to file: the title of the issue and its body."""

    title: str
    body: str


@dataclass(frozen=True, slots=True)
class FiledIssue:
    """One draft that intake decided: its title, and the number of the issue that it filed.

    Intake files no issue for a candidate that it skips, as it skips a possible duplicate, and it
    prints no number for that candidate, so `number` is None.
    """

    title: str
    number: int | None


def drafts_of(groups: Iterable[FindingGroup]) -> tuple[Draft, ...]:
    """The draft of each of `groups`, in their order."""
    return tuple(Draft(title=draft_title(group.name), body=draft_body(group)) for group in groups)


def draft_title(name: str) -> str:
    """The title of the draft of the group `name`: a defect of the scope `ai`, with a summary that
    intake accepts (#2346).

    The name of a group comes from a model and is masked here, as the body is, so a secret, a
    private host name and an email address of a name reach no issue (#2346, AGENTS.md rule 10).
    """
    return f"{_TITLE_LEAD}{_summary(sanitize_text(name))}"


def file_drafts(
    drafts: Sequence[Draft],
    runner: IntakeRunner = run_subprocess,
    *,
    cwd: Path | None = None,
) -> tuple[FiledIssue, ...]:
    """File each of `drafts` as an issue through `devops roadmap intake --confirm` (#2346).

    `runner` starts the child, as `run_subprocess` does, and `cwd` is the checkout whose roadmap
    intake reads. The run stops at the first draft that intake does not file, which raises
    `AgentAuditFilingError`.
    """
    filed: list[FiledIssue] = []
    with tempfile.TemporaryDirectory(prefix="agent-audit-") as folder:
        for number, draft in enumerate(drafts, start=1):
            body_file = _write_body(Path(folder), number, draft)
            result = runner(
                _intake_argv(draft.title, body_file),
                cwd=cwd,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
                quiet=True,
            )
            _raise_for_failure(draft, result)
            filed.append(FiledIssue(title=draft.title, number=_filed_number(result.stdout)))
    return tuple(filed)


def _intake_argv(title: str, body_file: Path) -> list[str]:
    """The argv that files `body_file` as an issue titled `title` (#2346)."""
    return [
        sys.executable,
        "-P",
        "-m",
        CONST_DEVOPS_CLI_ENTRY_MODULE,
        "roadmap",
        "intake",
        "--title",
        title,
        "--body-file",
        str(body_file),
        "--confirm",
    ]


def _write_body(folder: Path, number: int, draft: Draft) -> Path:
    """Write the body of `draft` to the file `number` of `folder`, and return its path."""
    path = folder / f"draft-{number}.md"
    path.write_text(draft.body, encoding="utf-8")
    return path


def _raise_for_failure(draft: Draft, result: subprocess.CompletedProcess[str]) -> None:
    """Raise `AgentAuditFilingError` when `result` says that intake did not file `draft`."""
    if result.returncode == 0:
        return
    raise AgentAuditFilingError(draft.title, status=result.returncode, detail=_detail(result))


def _detail(result: subprocess.CompletedProcess[str]) -> str:
    """The last line that the child printed, bounded, or `_NO_OUTPUT` when it printed none."""
    lines = [
        line.strip() for line in (result.stderr or result.stdout or "").splitlines() if line.strip()
    ]
    return (lines[-1] if lines else _NO_OUTPUT)[:_DETAIL_MAX_CHARS]


def _filed_number(output: str) -> int | None:
    """The number of the issue that intake filed, or None when its output names none."""
    found = _FILED_LINE.search(output)
    return int(found["number"]) if found is not None else None


def _summary(name: str) -> str:
    """The summary of the title: the words of `name` that fit `SUMMARY_MAX_CHARS`.

    Intake refuses a summary over the limit, so the words that do not fit are left out rather than
    cut. A name whose first word alone is too long gives `_FALLBACK_SUMMARY`, and its draft still
    names the problem in its body.
    """
    kept = ""
    for word in name.split():
        candidate = f"{kept} {word}".strip()
        if summary_length(candidate) > SUMMARY_MAX_CHARS:
            break
        kept = candidate
    return kept or _FALLBACK_SUMMARY


__all__ = ["Draft", "FiledIssue", "draft_title", "drafts_of", "file_drafts"]
