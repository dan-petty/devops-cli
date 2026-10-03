"""Planning documents, generated references and lockfiles stay off persona pages (#948).

In the branch reviews of release/v0.2.25 those paths took 58 of 214 persona pages (27%) and 77 of
319 (24%), and a hand triage of 23 reported findings on them found none valid. Path reviews, branch
reviews and pull request reviews decide it with one predicate. A routed file still reaches the
secret scan, and a change that routes every file makes no model call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.chunker import _extract_header_filenames, diff_pages
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import (
    ReviewClients,
    _collect_file_blocks,
    _execute_review_workflow,
    _prepare_branch_content,
    _prepare_pr_content,
)
from devops_cli.ai.review_schema import Finding
from devops_cli.commands.review import app as review_app
from devops_cli.security.base import ScanOutcome

_ROUTED = (
    "changelog.d/1.md",
    "docs/agent/tasks/task-1-x.md",
    "docs/ROADMAP.md",
    "docs/commands/ai.md",
    "docs/CLI_REFERENCE.md",
)
_TEXT = {
    "src/app.py": "def run() -> int:\n    return 1\n",
    **{rel: f"# {rel}\n\nPlanning notes.\n" for rel in _ROUTED},
}


def _diff(paths: tuple[str, ...]) -> str:
    """A unified diff adding each path with its text."""
    return "".join(
        f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel}\n"
        f"@@ -0,0 +1,{_TEXT[rel].count(chr(10))} @@\n"
        + "".join(f"+{line}\n" for line in _TEXT[rel].splitlines())
        for rel in paths
    )


def _page_files(pages: list[str]) -> list[str]:
    return sorted({name for page in pages for name in _extract_header_filenames(page)})


def _write(root: Path, paths: tuple[str, ...]) -> None:
    for rel in paths:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(_TEXT[rel], encoding="utf-8")


def _project(tmp_path: Path, git: Callable[..., None]) -> Path:
    """A repository holding the code and every routed file, uncommitted.

    It is a directory of its own: the test's own configuration sits in `tmp_path`.
    """
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q")
    _write(root, tuple(_TEXT))
    return root


def _branch(root: Path, git: Callable[..., None], changed: tuple[str, ...]) -> None:
    """A repository whose `feature` branch adds `changed` to `main`."""
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    git(root, "switch", "-qc", "feature")
    _write(root, changed)
    git(root, "add", ".")
    git(root, "commit", "-qm", "change")


def test_the_branch_page_builder_keeps_only_reviewable_files() -> None:
    """Verify a diff touching code, a changelog fragment, a task file, the roadmap and generated
    command references gives persona pages for the code alone."""
    assert _page_files(diff_pages(_diff(("src/app.py", *_ROUTED)))) == ["src/app.py"]


def test_a_branch_review_reaches_the_personas_with_only_reviewable_files(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify `devops review branch` pages hold only `src/app.py`."""
    root = tmp_path / "project"
    _branch(root, git, ("src/app.py", *_ROUTED))

    pages, *_ = _prepare_branch_content("feature", "main", root)

    assert _page_files(pages) == ["src/app.py"]


class _FakeGitHub:
    """A GitHub client serving one pull request that adds the six files."""

    def __init__(self, _token: str) -> None:
        self.pull = SimpleNamespace(
            title="Add the app and its paperwork",
            head=SimpleNamespace(sha="head", repo=SimpleNamespace(full_name="o/r")),
            base=SimpleNamespace(sha="base", ref="main", repo=SimpleNamespace(full_name="o/r")),
            get_files=lambda: [
                SimpleNamespace(filename=rel, status="added", previous_filename=None)
                for rel in _TEXT
            ],
        )

    def get_pull(self, _repo: str, _number: int) -> Any:
        return self.pull

    def get_pr_diff(self, _repo: str, _number: int) -> str:
        return _diff(tuple(_TEXT))

    def get_file_at(self, _repo: str, path: str, ref: str) -> str | None:
        return _TEXT.get(path) if ref == "head" else None

    def get_merge_base(self, _repo: str, _base: str, _head: str) -> str:
        return "base"


def test_a_pr_review_reaches_the_personas_with_only_reviewable_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops review pr` pages hold only `src/app.py`, offline against a fake client."""
    monkeypatch.setattr("devops_cli.github.client.GitHubClient", _FakeGitHub)

    pages, *_ = _prepare_pr_content(1, "o/r", "token", head_dir=tmp_path)

    assert _page_files(pages) == ["src/app.py"]


def test_a_path_review_skips_planning_and_generated_documents(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify a path review reads the code and leaves the routed files and lockfiles out."""
    root = _project(tmp_path, git)
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    assert _page_files(_collect_file_blocks(root, "*")) == ["src/app.py"]


def test_a_path_review_hands_its_routed_files_to_the_secret_scan(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """Verify `devops review path` gives the review workflow the files it routed, for the
    secret scan."""
    root = _project(tmp_path, git)
    with (
        patch("devops_cli.commands.review._make_review_clients"),
        patch("devops_cli.commands.review._init_logfire_if_enabled"),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]) as workflow,
    ):
        result = CliRunner().invoke(review_app, ["path", str(root)])

    assert (result.exit_code, sorted(workflow.call_args.kwargs["routed_files"])) == (
        0,
        sorted(_ROUTED),
    )


@pytest.fixture
def secret_scan(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[list[Path]]]:
    """Fake Gitleaks and Semgrep, recording the paths each reads; Gitleaks finds a secret in
    the changelog fragment."""
    seen: dict[str, list[list[Path]]] = {"Gitleaks": [], "Semgrep": []}

    def gitleaks(paths: list[Path], **_: Any) -> ScanOutcome:
        seen["Gitleaks"].append(list(paths))
        hits = [p for p in paths if p.name == "1.md"]
        return ScanOutcome(
            "ran",
            [
                Finding(
                    title="[GITLEAKS:generic-api-key] Secret in a changelog fragment",
                    location=f"{hit}:3",
                    severity="HIGH",
                )
                for hit in hits
            ],
        )

    def semgrep(paths: list[Path], **_: Any) -> ScanOutcome:
        seen["Semgrep"].append(list(paths))
        return ScanOutcome("ran", [])

    monkeypatch.setattr("devops_cli.security.gitleaks.run_gitleaks_scan", gitleaks)
    monkeypatch.setattr("devops_cli.security.semgrep.run_semgrep_scan", semgrep)
    monkeypatch.setattr(
        "devops_cli.security.bandit.run_bandit_scan", lambda *_, **__: ScanOutcome("ran")
    )
    return seen


def test_a_routed_file_still_reaches_the_secret_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, secret_scan: dict[str, list[list[Path]]]
) -> None:
    """Verify Gitleaks reads a changed `changelog.d/1.md` the personas never see, Semgrep does
    not, and the secret it finds lands in a payload of its own that persona review skips."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, ("src/app.py", "changelog.d/1.md"))
    client = MagicMock()
    client._config = None
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s948-routed",
        target_dir=tmp_path,
        llm_client=client,
        secret_scan_files=["changelog.d/1.md"],
    )

    reviewed: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_safe_review_file_payload",
        lambda _idx, _total, payload, *_, **__: reviewed.append(payload.file_path),
    )

    payloads = orchestrator.init_per_file_payloads(["src/app.py"], {})
    orchestrator.execute_multi_persona_review(payloads, {"src/app.py": _TEXT["src/app.py"]})

    assert (
        secret_scan["Gitleaks"],
        secret_scan["Semgrep"],
        {p.file_path: [f.title for f in p.findings] for p in payloads},
        reviewed,
    ) == (
        [[tmp_path / "src/app.py", tmp_path / "changelog.d/1.md"]],
        [[tmp_path / "src/app.py"]],
        {
            "src/app.py": [],
            "changelog.d/1.md": ["[GITLEAKS:generic-api-key] Secret in a changelog fragment"],
        },
        ["src/app.py"],
    )


def test_a_branch_with_only_routed_files_makes_no_model_call(
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    secret_scan: dict[str, list[list[Path]]],
) -> None:
    """Verify a branch that touches only `changelog.d/1.md` calls no model and never reaches
    the persona loop, still scans the fragment for secrets, and says nothing was left for the
    personas. The page builder yielded one empty page, the orchestrator found no files, and the
    legacy engine sent that page to the model."""
    root = tmp_path / "project"
    _branch(root, git, ("changelog.d/1.md",))
    pages, title, agents_md, target, base_revision = _prepare_branch_content(
        "feature", "main", root
    )
    model = MagicMock()
    printed: list[str] = []
    monkeypatch.setattr(
        "devops_cli.ai.review.runner.print_info", lambda text, **_: printed.append(text)
    )

    with patch("devops_cli.ai.review.runner._run_persona_loop", return_value=[]) as persona_loop:
        _execute_review_workflow(
            pages,
            title,
            MagicMock(),
            agents_md,
            False,
            None,
            False,
            ReviewClients(analysis=model, compose=model),
            target_type="branch",
            target_ref=target,
            target_dir=root,
            base_revision=base_revision,
        )

    assert (
        model.method_calls,
        persona_loop.called,
        secret_scan["Gitleaks"],
        any("Nothing is left for the personas" in line for line in printed),
    ) == ([], False, [[root / "changelog.d/1.md"]], True)


def _review_routed_branch(
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    stage_flags: ReviewStageFlags | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Review a branch touching only `changelog.d/1.md`; what was printed, and findings.json."""
    root = tmp_path / "project"
    _branch(root, git, ("changelog.d/1.md",))
    pages, title, agents_md, target, base_revision = _prepare_branch_content(
        "feature", "main", root
    )
    printed: list[str] = []
    monkeypatch.setattr(
        "devops_cli.ai.review.runner.print_info", lambda text, **_: printed.append(text)
    )
    model = MagicMock()
    _execute_review_workflow(
        pages,
        title,
        MagicMock(),
        agents_md,
        False,
        None,
        False,
        ReviewClients(analysis=model, compose=model),
        target_type="branch",
        target_ref=target,
        target_dir=root,
        stage_flags=stage_flags,
        base_revision=base_revision,
    )
    [written] = (tmp_path / ".data" / "reviews").glob("*/findings.json")
    return printed, json.loads(written.read_text(encoding="utf-8"))


def test_a_secret_in_a_routed_file_keeps_its_severity(
    tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a secret Gitleaks finds in a changelog fragment is reported at its severity, capped
    only because nothing verified it. The document cap made it LOW, hidden from the terminal,
    while the same secret in `src/` stayed HIGH: a review of routed files runs no verifier, so
    its secret could never be the verified one the cap spares."""

    def gitleaks(paths: list[Path], **_: Any) -> ScanOutcome:
        return ScanOutcome(
            "built-in patterns",
            [
                Finding(
                    title="[GITLEAKS] Secret detected: OpenAI API Key",
                    location=f"{path}:3",
                    severity="CRITICAL",
                )
                for path in paths
            ],
        )

    monkeypatch.setattr("devops_cli.security.gitleaks.run_gitleaks_scan", gitleaks)

    _, written = _review_routed_branch(tmp_path, git, monkeypatch)

    assert [
        (f["title"], f["severity"], f["severity_raw"], f["status"]) for f in written["findings"]
    ] == [("[GITLEAKS] Secret detected: OpenAI API Key", "HIGH", "CRITICAL", "UNVERIFIED")]


@pytest.mark.usefixtures("secret_scan")
def test_a_review_of_routed_files_records_no_persona(
    tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify findings.json names no persona when none ran; it named devsecops, architect and
    qa."""
    _, written = _review_routed_branch(tmp_path, git, monkeypatch)

    assert written["personas"] == []


def test_a_review_of_routed_files_without_the_static_scan_says_nothing_was_scanned(
    tmp_path: Path,
    git: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    secret_scan: dict[str, list[list[Path]]],
) -> None:
    """Verify `--no-static-scan` on a review of routed files says the static scan was off, and
    Gitleaks reads nothing; it said the secret scan still read them."""
    printed, _ = _review_routed_branch(
        tmp_path, git, monkeypatch, stage_flags=ReviewStageFlags(static_scan=False)
    )

    assert (
        secret_scan["Gitleaks"],
        any("secret scan still reads" in line for line in printed),
        any("The static scan is off, so none of the 1 is read." in line for line in printed),
    ) == ([], False, True)
