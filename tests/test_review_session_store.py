"""The review session store: the one place that says where review sessions live (#771)."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import FileReviewPayload, ReviewSessionPayload, SavedFinding
from devops_cli.config.constants import (
    CONST_ERROR_CODE_REVIEW_SESSION_EXISTS,
    CONST_ERROR_CODE_SECURITY,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions import SecurityError
from devops_cli.exceptions.ai import ReviewSessionExistsError
from devops_cli.review.session import ReviewSession, ReviewSessionStore
from devops_cli.ui.data_providers import fetch_review_status


def test_sessions_live_in_the_reviews_directory_of_the_data_directory_variable(
    isolate_data_dir: Path,
) -> None:
    """Verify `DEVOPS_CLI_DATA_DIR` names the data directory whose `reviews` holds the sessions."""
    assert ReviewSessionStore.root() == isolate_data_dir / "reviews"


def test_a_relative_data_directory_variable_is_under_the_review_data_root(
    monkeypatch: pytest.MonkeyPatch, isolate_user_data_root: Path
) -> None:
    """Verify a relative `DEVOPS_CLI_DATA_DIR` resolves where a review resolves its data (#972),
    so a command run from another directory finds the sessions a review wrote."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "kept")

    assert ReviewSessionStore.root() == isolate_user_data_root / "kept" / "reviews"


@pytest.mark.parametrize("set_by", ["environment", "config file"])
def test_sessions_live_where_the_reviews_directory_setting_points(
    set_by: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
) -> None:
    """Verify without `DEVOPS_CLI_DATA_DIR`, `data.reviews_dir` says where the sessions are,
    whether `DEVOPS_CLI_DATA_REVIEWS_DIR` or the config file sets it."""
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR")
    if set_by == "environment":
        monkeypatch.setenv("DEVOPS_CLI_DATA_REVIEWS_DIR", str(elsewhere))
        config(data={"dir": str(tmp_path / "data")})
    else:
        config(data={"dir": str(tmp_path / "data"), "reviews_dir": str(elsewhere)})

    assert ReviewSessionStore.root() == elsewhere


def test_the_store_root_is_created_by_writing_a_session_not_by_asking_for_it(
    isolate_data_dir: Path,
) -> None:
    """Verify naming the root creates no directory, so a command that only reads sessions
    leaves a data directory without reviews as it found it."""
    root = ReviewSessionStore.root()

    assert (root.exists(), list(isolate_data_dir.iterdir())) == (False, [])


REFUSED_DATA_DIRECTORIES = [
    pytest.param("../../../outside", id="traversal"),
    pytest.param("/etc", id="system-directory"),
]


@pytest.mark.parametrize("data_dir", REFUSED_DATA_DIRECTORIES)
def test_the_store_root_refuses_a_directory_a_session_may_not_be_kept_in(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a traversal sequence or a host system directory in the data directory is refused
    with a security error, whichever command resolved the root."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", data_dir)

    with pytest.raises(SecurityError) as refused:
        ReviewSessionStore.root()

    assert (refused.value.exit_code, refused.value.error_code) == (
        CONST_EXIT_FAILURE,
        CONST_ERROR_CODE_SECURITY,
    )


@pytest.mark.parametrize("data_dir", REFUSED_DATA_DIRECTORIES)
def test_the_review_summary_has_no_session_when_the_store_root_is_refused(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the review summary is empty for a refused directory, not a crash."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", data_dir)

    assert fetch_review_status().has_session is False


def _payload(*titles: str) -> ReviewSessionPayload:
    """A session payload reporting one finding per title."""
    return ReviewSessionPayload(
        generated_at="2026-10-22T12:00:00Z",
        findings=[
            SavedFinding(location=f"src/a.py:{line}", title=title, description="d")
            for line, title in enumerate(titles, start=1)
        ],
    )


def _published(store: type[ReviewSessionStore], name: str, *titles: str) -> ReviewSession:
    """A session that wrote its findings and was published."""
    session = store.session(name)
    session.write_findings(_payload(*titles))
    session.publish()
    return session


def test_the_review_summary_reads_the_session_published_under_the_store_root(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a session published under the store root is the one the review summary reads."""
    _published(review_store, "20261001-120000", "Kept")

    summary = fetch_review_status()

    assert (summary.session_name, summary.total_findings) == ("20261001-120000", 1)


def test_the_review_summary_does_not_present_an_in_flight_session_as_the_result(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a review that has written its findings but is not yet published is not
    presented as a completed result (#771)."""
    _published(review_store, "20261001-120000", "Kept")
    review_store.session("20261002-120000").write_findings(_payload("Kept"))

    assert fetch_review_status().session_name == "20261001-120000"


def test_a_session_is_listed_only_once_it_is_published(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a session being written is not a session, to the store or to a reader that looks
    for `findings.json` under the sessions directory, until it is published whole."""
    session = review_store.session("20261001-120000")
    session.write_findings(_payload("Kept"))
    session.write_report("# Report\n")

    while_writing = (
        review_store.sessions(),
        review_store.latest(),
        [session.name for session in review_store.in_flight()],
        list(review_store.root().glob("*/findings.json")),
    )
    session.publish()

    assert (
        while_writing,
        [listed.name for listed in review_store.sessions()],
        review_store.in_flight(),
        list(review_store.root().glob("*/findings.json")),
    ) == (
        ([], None, ["20261001-120000"], []),
        ["20261001-120000"],
        [],
        [session.findings_path],
    )


def test_a_published_session_holds_every_file_the_review_wrote(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify publishing moves the whole staging directory, so a review of routed files only,
    which writes no profile, publishes the files it wrote, and no staging directory is left."""
    session = review_store.session("20261001-120000")
    session.create()
    session.write_findings(_payload("Kept"))
    session.write_raised(_payload("Kept"))
    session.write_sarif({"version": "2.1.0", "runs": []})
    session.write_report("# Report\n")
    session.write_payload(FileReviewPayload(file_path="src/a.py"))

    published = session.publish()

    assert (
        sorted(path.name for path in published.iterdir()),
        len(list((published / "files").glob("*.json"))),
        list(review_store.root().glob(".staging/*")),
    ) == (
        ["candidates.json", "files", "findings.json", "findings.sarif", "review.md"],
        1,
        [],
    )


def test_publishing_a_name_that_is_already_published_is_refused(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a second review of one name does not merge into the first: the first stays as it
    was, the refusal is typed, and the second review's files stay in staging."""
    first = _published(review_store, "20261001-120000", "First")
    second = review_store.session("20261001-120000")
    second.create()
    second.write_findings(_payload("Second"))

    with pytest.raises(ReviewSessionExistsError) as refused:
        second.publish()

    assert (
        refused.value.exit_code,
        refused.value.error_code,
        first.findings_path.read_text(encoding="utf-8"),
        (second.staging / "findings.json").is_file(),
    ) == (
        CONST_EXIT_FAILURE,
        CONST_ERROR_CODE_REVIEW_SESSION_EXISTS,
        _payload("First").model_dump_json(indent=2),
        True,
    )


def test_creating_a_session_clears_what_a_failed_review_of_that_name_left_behind(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify the files of a review that died part-way are not published with the next review
    of the same name."""
    failed = review_store.session("20261001-120000")
    failed.write_findings(_payload("Stale"))
    failed.write_report("# Stale\n")
    retry = review_store.session("20261001-120000")

    retry.create()
    retry.write_findings(_payload("Fresh"))
    published = retry.publish()

    assert (
        sorted(path.name for path in published.iterdir()),
        (published / "findings.json").read_text(encoding="utf-8"),
    ) == (["files", "findings.json"], _payload("Fresh").model_dump_json(indent=2))


def test_the_store_lists_only_the_directories_that_are_sessions(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify the benchmarks and corpora kept in the sessions directory, and a hidden
    directory, are not sessions, so none is the latest although `corpora` sorts after every
    timestamp, and the review summary does not show one in place of a review."""
    _published(review_store, "20261001-120000", "Kept")
    for kept_beside_sessions in ("benchmarks", "corpora", ".cache"):
        (review_store.root() / kept_beside_sessions).mkdir()

    latest = review_store.latest()

    assert (
        [session.name for session in review_store.sessions()],
        latest.name if latest else None,
        fetch_review_status().session_name,
    ) == (["20261001-120000"], "20261001-120000", "20261001-120000")


def test_sessions_are_listed_newest_first_and_the_latest_is_the_newest(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify the order is by session name, the review's timestamp, not by directory
    modification time, which a verdict written into an old session moves."""
    for name in ("20261001-120000", "20261003-120000", "20261002-120000"):
        _published(review_store, name, "Kept")
    os.utime(review_store.root() / "20261001-120000", (4_000_000_000, 4_000_000_000))

    latest = review_store.latest()

    assert (
        [session.name for session in review_store.sessions()],
        latest.name if latest else None,
    ) == (["20261003-120000", "20261002-120000", "20261001-120000"], "20261003-120000")


def test_a_session_written_before_staging_is_a_session(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a directory that holds findings.json and was never staged is listed, and is the
    latest, with no migration."""
    old = review_store.root() / "20260101-120000"
    old.mkdir()
    (old / "findings.json").write_text(_payload("Kept").model_dump_json(), encoding="utf-8")

    latest = review_store.latest()

    assert (
        [session.name for session in review_store.sessions()],
        latest.name if latest else None,
    ) == (["20260101-120000"], "20260101-120000")


def test_the_store_has_no_sessions_before_a_review_has_written_one(
    isolate_data_dir: Path,
) -> None:
    """Verify listing and finding the latest session on a data directory that was never
    reviewed neither fail nor create the sessions directory."""
    assert (
        ReviewSessionStore.sessions(),
        ReviewSessionStore.in_flight(),
        ReviewSessionStore.latest(),
        ReviewSessionStore.root().exists(),
    ) == ([], [], None, False)


def test_the_session_files_keep_the_text_the_models_serialise_to(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify the files hold the models' own JSON, indented, so a reader of sessions already
    written reads the new ones unchanged."""
    session = review_store.session("20261001-120000")
    payload = _payload("Kept")
    file_payload = FileReviewPayload(file_path="src/a.py")
    session.write_findings(payload)
    session.write_payload(file_payload)
    published = session.publish()

    (record,) = (published / "files").glob("*.json")
    assert (
        (published / "findings.json").read_text(encoding="utf-8"),
        record.read_text(encoding="utf-8"),
    ) == (payload.model_dump_json(indent=2), file_payload.model_dump_json(indent=2))


def test_the_session_files_are_as_readable_as_a_written_text_file_is(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a session file is mode 0644 under the usual umask, as `write_text` leaves one, not
    the 0600 of the temporary file an atomic write renames into place."""
    session = review_store.session("20261001-120000")
    previous_umask = os.umask(0o022)
    try:
        session.write_findings(_payload("Kept"))
        published = session.publish()
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE((published / "findings.json").stat().st_mode) == 0o644


@pytest.mark.parametrize(
    "file_path",
    [
        pytest.param("a%00b.py", id="percent-encoded-nul"),
        pytest.param("%2e%2e%2fx.py", id="percent-encoded-traversal"),
        pytest.param("..\\x.py", id="backslash-traversal"),
        pytest.param("src/a.py", id="plain"),
    ],
)
def test_a_file_is_recorded_whatever_its_path_is_named(
    file_path: str, review_store: type[ReviewSessionStore]
) -> None:
    """Verify the record of a file is written for a repository path that a path validator would
    read as traversal after decoding it, since the session names the record, not the path."""
    session = review_store.session("20261001-120000")

    session.write_payload(FileReviewPayload(file_path=file_path))
    published = session.publish()

    (record,) = (published / "files").glob("*.json")
    assert FileReviewPayload.model_validate_json(record.read_text("utf-8")).file_path == file_path


def test_two_paths_that_flatten_alike_are_recorded_apart(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify `src/a_b.py` and `src/a/b.py`, which a flattened name would make one file and one
    overwrite the other, are two records."""
    session = review_store.session("20261001-120000")

    session.write_payload(FileReviewPayload(file_path="src/a_b.py"))
    session.write_payload(FileReviewPayload(file_path="src/a/b.py"))
    published = session.publish()

    assert sorted(
        FileReviewPayload.model_validate_json(record.read_text("utf-8")).file_path
        for record in (published / "files").glob("*.json")
    ) == ["src/a/b.py", "src/a_b.py"]
