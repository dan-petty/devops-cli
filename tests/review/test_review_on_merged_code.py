"""A review session records the checkout it read, and says whether it is on merged code (#2415).

When a review starts, the session records the commit of the checkout that holds its target and
whether the working tree was clean. A session is on merged code when it reviewed a path, its tree
was clean, and its commit is on `origin/main`. Git runs for real in temporary repositories.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.ai.review_schema import ReviewCheckout, ReviewSessionPayload, SavedFinding
from devops_cli.exceptions import GitOperationError
from devops_cli.review.checkout import is_on_merged_code, read_checkout
from devops_cli.review.session import ReviewSession, ReviewSessionStore


def _head(repo: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _repository(root: Path, git: Callable[..., None]) -> Path:
    """A checkout with one commit, which `origin/main` also names."""
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    return root


def _session(subject_type: str, checkout: ReviewCheckout | None) -> ReviewSessionPayload:
    return ReviewSessionPayload(subject={"type": subject_type, "ref": "src"}, checkout=checkout)


@pytest.mark.parametrize("edit", [None, "tracked", "untracked"])
def test_a_path_review_records_the_commit_and_the_clean_tree_it_read(
    tmp_path: Path,
    git: Callable[..., None],
    cli: Callable[..., Any],
    review_store: type[ReviewSessionStore],
    monkeypatch: pytest.MonkeyPatch,
    edit: str | None,
) -> None:
    """Verify `devops review path` writes the head commit of the reviewed checkout, and whether
    its tree was clean, into findings.json and candidates.json."""
    root = _repository(tmp_path / "project", git)
    if edit == "tracked":
        (root / "src" / "app.py").write_text("def run() -> int:\n    return 2\n", encoding="utf-8")
    elif edit == "untracked":
        (root / "src" / "new.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = cli("review", "path", str(root / "src"), "--reporting-only")

    [session] = [written.parent for written in review_store.root().glob("*/findings.json")]
    recorded = [
        json.loads((session / name).read_text(encoding="utf-8"))["checkout"]
        for name in ("findings.json", "candidates.json")
    ]
    expected = {"head": _head(root), "clean": edit is None}
    assert (result.exit_code, recorded) == (0, [expected, expected])


def test_a_target_outside_any_checkout_or_before_its_first_commit_has_no_checkout(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a directory outside any checkout, and a checkout with no commit yet, record none."""
    outside = tmp_path / "plain"
    outside.mkdir()
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q", "-b", "main")

    assert (read_checkout(outside), read_checkout(empty)) == (None, None)


@pytest.mark.parametrize(
    ("subject_type", "clean", "on_main", "merged"),
    [
        ("path", True, True, True),
        ("pr", True, True, False),
        ("branch", True, True, False),
        ("path", False, True, False),
        ("path", True, False, False),
    ],
    ids=["path-on-main", "pr", "branch", "dirty-tree", "head-off-main"],
)
def test_only_a_clean_path_review_of_a_commit_on_main_is_on_merged_code(
    tmp_path: Path,
    git: Callable[..., None],
    subject_type: str,
    clean: bool,
    on_main: bool,
    merged: bool,
) -> None:
    """Verify the merged-code predicate for each target type, a dirty tree and a head that
    `origin/main` does not hold."""
    root = _repository(tmp_path / "project", git)
    if not on_main:
        git(root, "switch", "-q", "-c", "feature")
        git(root, "commit", "-q", "--allow-empty", "-m", "on the topic branch")

    session = _session(subject_type, ReviewCheckout(head=_head(root), clean=clean))

    assert is_on_merged_code(session, root) is merged


def test_a_session_without_a_checkout_is_not_on_merged_code(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a path session written before #2415, or outside any checkout, is not on merged
    code, and that no git command decides it."""
    root = _repository(tmp_path / "project", git)

    assert is_on_merged_code(_session("path", None), root) is False


def test_a_head_that_the_repository_does_not_hold_is_refused(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a session whose commit is unknown in the repository raises a git error and is not
    read as off main."""
    root = _repository(tmp_path / "project", git)
    session = _session("path", ReviewCheckout(head="0" * 40, clean=True))

    with pytest.raises(GitOperationError) as raised:
        is_on_merged_code(session, root)

    assert (raised.value.exit_code, raised.value.error_code) == (1, "GIT_OPERATION_ERROR")


@pytest.mark.parametrize("head", ["--upload-pack=touch x", "HEAD", "abc123", "A" * 40])
def test_a_recorded_head_must_be_a_full_commit_name(head: str) -> None:
    """Verify findings.json cannot hand git an option or a symbolic name as the session's commit."""
    with pytest.raises(ValidationError) as raised:
        ReviewCheckout(head=head, clean=True)
    assert len(raised.value.errors()) > 0


def test_review_verify_keeps_the_session_checkout(
    review_store: type[ReviewSessionStore], cli: Callable[..., Any]
) -> None:
    """Verify `devops review verify` rewrites findings.json with the session's checkout."""
    checkout = ReviewCheckout(head="a" * 40, clean=True)
    session = ReviewSession(review_store.root() / "20261028-090000")
    session.write_findings(
        ReviewSessionPayload(
            subject={"type": "path", "ref": "src"},
            checkout=checkout,
            findings=[SavedFinding(title="Hardcoded Token", location="auth.py:42")],
        )
    )
    published = session.publish()

    result = cli(
        "review", "verify", published.name, "--index", "1", "--status", "VERIFIED", "--reason", "x"
    )

    saved = json.loads((published / "findings.json").read_text(encoding="utf-8"))
    assert (result.exit_code, saved["checkout"]) == (0, checkout.model_dump(mode="json"))
