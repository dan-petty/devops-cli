"""A review command reports a session file that does not validate in one error line (#2644)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.review.defects import CORPUS_MANIFEST
from devops_cli.review.session import ReviewSessionStore

_SESSION = "20261001-000000"
_FIELD = "network_references.0.reputation.outcome"
_OLD_NETWORK_REFERENCE = {
    "target": "203.0.113.7",
    "reference_type": "ip",
    "reputation": {
        "target": "203.0.113.7",
        "ip": "203.0.113.7",
        "reputation_summary": "Clean",
    },
}


def _command(name: str, corpus: Path) -> list[str]:
    commands = {
        "findings": ["review", "findings", _SESSION],
        "verify": ["review", "verify", _SESSION, "--index", "1", "--status", "INVALIDATED"]
        + ["--reason", "x"],
        "intake": ["review", "intake", _SESSION, "--repo", "octo/repo", "--dry-run"],
        "corpus-score": ["review", "corpus", "score", str(corpus), "--session", _SESSION],
    }
    return commands[name]


@pytest.mark.parametrize("name", ["findings", "verify", "intake", "corpus-score"])
def test_a_command_reports_an_invalid_session_file_in_one_error_line(
    name: str,
    tmp_path: Path,
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify each reader exits 1 with one line that holds the file path and the failing field."""
    session = review_store.root() / _SESSION
    session.mkdir(parents=True)
    findings = session / "findings.json"
    findings.write_text(
        json.dumps({"findings": [], "network_references": [_OLD_NETWORK_REFERENCE]}),
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / CORPUS_MANIFEST).write_text(
        json.dumps({"sources": [], "seed": 1, "created_at": "2026-10-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    # `review intake` needs a checkout to run in; it reads the session before it uses git.
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    result = cli(*_command(name, corpus))

    lines = [line for line in result.output.splitlines() if line.strip()]
    flat = " ".join(result.output.split())
    assert (
        result.exit_code,
        type(result.exception),
        len(lines),
        str(findings) in flat,
        _FIELD in flat,
    ) == (1, SystemExit, 1, True, True)
