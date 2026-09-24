"""Open-source sample repositories pinned by commit (#502).

The catalog must cover every category with permissively licensed repositories pinned to exact
commits. A fetch takes only the pinned commit and verifies the commit, licence files and paths.
Fetches here come from local repositories, so no test touches the network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from devops_cli.ai.review.samples import (
    SampleCatalog,
    SampleCategory,
    SampleRepository,
    checkout_problems,
    fetch_sample,
    load_sample_catalog,
    samples_dir,
)
from devops_cli.commands import review as review_commands
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def upstream(tmp_path: Path) -> tuple[Path, str, str]:
    """A local repository with two commits: the pinned one, and a later one."""
    repo = tmp_path / "upstream"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "--quiet")
    (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "pinned")
    pinned = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")
    _git(repo, "commit", "--quiet", "-am", "later")
    return repo, pinned, _git(repo, "rev-parse", "HEAD")


def _sample(repo: Path, commit: str, **changes: object) -> SampleRepository:
    fields: dict[str, object] = {
        "name": "local",
        "category": "python",
        "languages": ["python"],
        "repository": repo.as_uri(),
        "commit": commit,
        "license": "MIT",
        "license_files": ["LICENSE"],
        "paths": ["src"],
    }
    return SampleRepository.model_validate(fields | changes)


def test_the_catalog_covers_every_category() -> None:
    """Verify each category of technical project has at least one sample."""
    catalog = load_sample_catalog()

    assert {sample.category for sample in catalog.samples} == set(SampleCategory)


def test_every_sample_is_on_github_pinned_and_permissively_licensed() -> None:
    """Verify the checked-in entries fetch over HTTPS from GitHub at exact commits."""
    samples = load_sample_catalog().samples

    assert [
        s.name
        for s in samples
        if not s.repository.startswith("https://github.com/") or len(s.commit) != 40
    ] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("license", "GPL-3.0-only"),
        ("license", "MIT OR GPL-2.0-only"),
        ("commit", "main"),
        ("commit", "v1.2.3"),
        ("repository", "http://github.com/o/r"),
        ("repository", "ext::sh -c touch% /tmp/x"),
        ("paths", ["../outside"]),
        ("license_files", ["/etc/passwd"]),
        ("name", "../escape"),
    ],
)
def test_an_entry_outside_the_policy_is_rejected(field: str, value: object) -> None:
    """Verify copyleft licences, moving refs, other transports and escaping paths are refused."""
    with pytest.raises(ValidationError):
        _sample(Path("/tmp/repo"), **{"commit": "a" * 40, field: value})


def test_a_dual_licence_of_permissive_licences_is_accepted() -> None:
    """Verify an SPDX expression is permissive when every licence in it is."""
    sample = _sample(Path("/tmp/repo"), "a" * 40, license="MIT OR Apache-2.0")

    assert sample.license == "MIT OR Apache-2.0"


def test_sample_names_are_unique() -> None:
    """Verify a catalog naming two samples alike is refused, since each is a directory."""
    sample = _sample(Path("/tmp/repo"), "a" * 40)

    with pytest.raises(ValidationError):
        SampleCatalog(samples=[sample, sample])


def test_selecting_by_name_and_category() -> None:
    """Verify selection by name, by category, and refusal of an unknown name."""
    catalog = load_sample_catalog()

    selected = (
        [s.name for s in catalog.select(["cobra", "click"])],
        {s.category for s in catalog.select(category=SampleCategory.C_CPP)},
    )

    assert selected == (["click", "cobra"], {SampleCategory.C_CPP})
    with pytest.raises(ValueError, match="no sample named nope"):
        catalog.select(["nope"])


def test_a_fetch_takes_the_pinned_commit_and_verifies_it(
    tmp_path: Path, upstream: tuple[Path, str, str]
) -> None:
    """Verify the checkout is at the pinned commit, not the upstream head, with its files."""
    repo, pinned, _ = upstream
    sample = _sample(repo, pinned)

    problems = fetch_sample(sample, tmp_path / "samples")

    checkout = tmp_path / "samples" / "local"
    assert (problems, _git(checkout, "rev-parse", "HEAD")) == ([], pinned)
    assert (checkout / "src" / "app.py").read_text(encoding="utf-8") == "x = 1\n"
    assert _git(checkout, "rev-list", "--count", "HEAD") == "1"


def test_a_fetched_sample_is_not_fetched_again(
    tmp_path: Path, upstream: tuple[Path, str, str]
) -> None:
    """Verify a checkout already at its commit needs no network: the upstream may be gone."""
    repo, pinned, _ = upstream
    sample = _sample(repo, pinned)
    fetch_sample(sample, tmp_path / "samples")
    repo.rename(tmp_path / "gone")

    assert fetch_sample(sample, tmp_path / "samples") == []


def test_a_checkout_at_another_commit_is_moved_to_the_pinned_one(
    tmp_path: Path, upstream: tuple[Path, str, str]
) -> None:
    """Verify a stale checkout is detected and fetched to the catalog's commit."""
    repo, pinned, later = upstream
    fetch_sample(_sample(repo, later), tmp_path / "samples")
    sample = _sample(repo, pinned)
    checkout = tmp_path / "samples" / "local"

    before = checkout_problems(sample, checkout)
    after = fetch_sample(sample, tmp_path / "samples")

    assert (before, after, _git(checkout, "rev-parse", "HEAD")) == (
        [f"not at {pinned[:12]}"],
        [],
        pinned,
    )


def test_a_missing_licence_file_or_path_is_reported(
    tmp_path: Path, upstream: tuple[Path, str, str]
) -> None:
    """Verify the checkout is checked for the licence files and paths the entry names."""
    repo, pinned, _ = upstream
    sample = _sample(repo, pinned, license_files=["COPYING"], paths=["src", "lib"])

    problems = fetch_sample(sample, tmp_path / "samples")

    assert problems == ["licence file COPYING is missing", "path lib is missing"]


def test_a_commit_the_repository_lacks_fails_the_fetch(
    tmp_path: Path, upstream: tuple[Path, str, str]
) -> None:
    """Verify an unknown commit is a failed fetch, not an empty checkout."""
    repo, _, _ = upstream

    problems = fetch_sample(_sample(repo, "0" * 40), tmp_path / "samples")

    assert len(problems) == 1 and problems[0].startswith("fetch failed: ")


def test_samples_live_under_the_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the samples directory follows DEVOPS_CLI_DATA_DIR."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    assert samples_dir() == (tmp_path / "samples").resolve()


def test_the_list_command_shows_every_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops review samples list` shows the catalog and that nothing is fetched."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    result = cli.invoke(app, ["review", "samples", "list", "--category", "c-cpp"])

    assert result.exit_code == 0, result.output
    assert ("cjson" in result.output, "fmt" in result.output, "cobra" in result.output) == (
        True,
        True,
        False,
    )


def test_the_fetch_command_refuses_an_unknown_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an unknown name fails before anything is fetched."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    result = cli.invoke(app, ["review", "samples", "fetch", "nope"])

    assert (result.exit_code, "no sample named nope" in result.output) == (1, True)
    assert not (tmp_path / "samples").exists()


def test_a_dry_run_fetch_fetches_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a dry run names what it would fetch and touches nothing."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(review_commands, "is_dry_run", lambda: True)

    result = cli.invoke(app, ["review", "samples", "fetch", "cobra"])

    assert (result.exit_code, "Would fetch https://github.com/spf13/cobra" in result.output) == (
        0,
        True,
    )
    assert not (tmp_path / "samples").exists()
