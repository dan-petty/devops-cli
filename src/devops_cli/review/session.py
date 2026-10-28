"""The review session store: where review sessions live on disk and how a review writes one (#771).

Every command that writes or reads a review session finds the sessions directory here, so a
review, the dashboard and the history figures cannot disagree about where it is. A review writes
its session through a `ReviewSession`, into a private staging directory beside the sessions, and
publishes it with one rename: a session in the sessions directory is whole, and one being written,
or abandoned part-way, is not in it.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from devops_cli.config.constants import (
    CONST_REVIEW_ANALYSIS_FILENAME,
    CONST_REVIEW_CANDIDATES_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_REVIEW_PAGES_DIRNAME,
    CONST_REVIEW_PROFILE_FILENAME,
    CONST_REVIEW_REPORT_FILENAME,
    CONST_REVIEW_SARIF_FILENAME,
    CONST_REVIEW_STAGING_DIRNAME,
    CONST_REVIEWS_DIR_NAME,
)
from devops_cli.config.env import env_var_for_option
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
from devops_cli.core.repo import resolve_review_data_path
from devops_cli.exceptions import SecurityError
from devops_cli.exceptions.ai import ReviewSessionExistsError
from devops_cli.output.file_writer import write_file

if TYPE_CHECKING:
    from devops_cli.ai.review.profile import ReviewProfile
    from devops_cli.ai.review_schema import FileReviewPayload, ReviewSessionPayload
    from devops_cli.review.analysis import AnalysisReport


@dataclass(frozen=True)
class ReviewSession:
    """One review session: written into a staging directory, then published whole.

    `directory` is where the session lives once published. Every writer returns the path its file
    has there, which exists only after `publish()`.
    """

    directory: Path

    @property
    def name(self) -> str:
        """The session's id, a timestamp unless the review was given one."""
        return self.directory.name

    @property
    def staging(self) -> Path:
        """Where the session is written, beside the sessions so that publishing is a rename.

        A level below the sessions directory, so that a reader that looks for `findings.json`
        one level down never finds it here.
        """
        return self.directory.parent / CONST_REVIEW_STAGING_DIRNAME / self.name

    @property
    def findings_path(self) -> Path:
        """The findings the review reports."""
        return self.directory / CONST_REVIEW_FINDINGS_FILENAME

    @property
    def report_path(self) -> Path:
        """The Markdown report."""
        return self.directory / CONST_REVIEW_REPORT_FILENAME

    def create(self) -> None:
        """Start the session's staging directory, clearing what an earlier review of that name
        left in it."""
        self.discard()
        (self.staging / CONST_REVIEW_PAGES_DIRNAME).mkdir(parents=True)

    def discard(self) -> None:
        """Remove the session's staging directory and what a review wrote in it, if there is one."""
        if self.staging.exists():
            shutil.rmtree(self.staging)

    def write_findings(self, payload: ReviewSessionPayload) -> Path:
        """Write the findings the review reports."""
        return self._write_model(CONST_REVIEW_FINDINGS_FILENAME, payload)

    def write_raised(self, payload: ReviewSessionPayload) -> Path:
        """Write every finding the review raised, each with its verification status."""
        return self._write_model(CONST_REVIEW_CANDIDATES_FILENAME, payload)

    def write_sarif(self, document: Mapping[str, Any]) -> Path:
        """Write the admitted tool findings as a SARIF document."""
        return self._write_text(CONST_REVIEW_SARIF_FILENAME, json.dumps(document, indent=2) + "\n")

    def write_report(self, markdown: str) -> Path:
        """Write the Markdown report."""
        return self._write_text(CONST_REVIEW_REPORT_FILENAME, markdown)

    def write_profile(self, profile: ReviewProfile) -> Path:
        """Write where the review's time went."""
        return self._write_model(CONST_REVIEW_PROFILE_FILENAME, profile)

    def write_analysis(self, report: AnalysisReport) -> Path:
        """Write the model analysis of the admitted tool findings' groups."""
        return self._write_model(CONST_REVIEW_ANALYSIS_FILENAME, report)

    def write_payload(self, payload: FileReviewPayload) -> Path:
        """Write the record of one file the review read.

        The record is named by a digest of the file's path, which is the same length whatever
        the path holds and names no two files alike. A flattened path could not do either:
        `src/a_b.py` and `src/a/b.py` were one name, and a path validator reads `%2e%2e%2f` in
        a name as traversal. The file's path is in the record.
        """
        digest = hashlib.sha256(payload.file_path.encode()).hexdigest()
        return self._write_model(Path(CONST_REVIEW_PAGES_DIRNAME) / f"{digest}.json", payload)

    def publish(self) -> Path:
        """Make the session visible, whole, by renaming its staging directory to its name.

        Raises:
            ReviewSessionExistsError: A session of that name is already published. The review's
                files stay in staging.
        """
        try:
            self.staging.rename(self.directory)
        except OSError as exc:
            if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                raise
            raise ReviewSessionExistsError(self.name, staging=str(self.staging)) from exc
        return self.directory

    def _write_model(self, name: str | Path, model: BaseModel) -> Path:
        return self._write_text(name, model.model_dump_json(indent=2))

    def _write_text(self, name: str | Path, text: str) -> Path:
        """Write a file of the staging directory, readable as `write_text` leaves a file.

        Staging is private until published, so the file needs no temporary file and rename of its
        own, which would leave it readable by its owner alone.
        """
        write_file(
            self.staging / name, text, format_type="text", atomic=False, base_dir=self.staging
        )
        return self.directory / name


class ReviewSessionStore:
    """Where review sessions are kept."""

    @staticmethod
    def root() -> Path:
        """The directory holding review sessions, resolved and not created.

        `DEVOPS_CLI_DATA_DIR`, when set, holds them in its `reviews`; otherwise `data.reviews_dir`
        says where. A relative path is under the review data root, where a review keeps its data
        whichever directory the command runs from (`resolve_review_data_path`, #972). Reading
        never creates the directory: writing a session does.

        Raises:
            SecurityError: The path holds a traversal sequence or is a host system directory.
        """
        data_dir = os.environ.get(env_var_for_option("data.dir") or "")
        configured = (
            Path(data_dir) / CONST_REVIEWS_DIR_NAME
            if data_dir
            else load_settings().data.reviews_dir
        )
        validate_no_path_traversal(configured, label="Review sessions directory")
        root = resolve_review_data_path(configured).resolve()
        if is_forbidden_system_path(root):
            raise SecurityError(f"Review sessions directory {root} is a forbidden system path")
        return root

    @staticmethod
    def session(name: str) -> ReviewSession:
        """The session of that name, whether or not a review has written it yet."""
        return ReviewSession(ReviewSessionStore.root() / name)

    @staticmethod
    def sessions() -> list[ReviewSession]:
        """Every published session, newest first.

        A directory of the sessions directory is a session when it holds `findings.json`, which
        every published session does: benchmarks and corpora are kept there too. Names are
        timestamps, so a reverse sort of them is a reverse chronological one, which the
        directories' modification times are not: a verdict written into an old session moves its.
        """
        root = ReviewSessionStore.root()
        return [s for s in ReviewSessionStore._named_in(root, root) if s.findings_path.is_file()]

    @staticmethod
    def in_flight() -> list[ReviewSession]:
        """Every session a review is writing, or abandoned part-way, newest first."""
        root = ReviewSessionStore.root()
        return ReviewSessionStore._named_in(root / CONST_REVIEW_STAGING_DIRNAME, root)

    @staticmethod
    def latest() -> ReviewSession | None:
        """The newest published session."""
        return next(iter(ReviewSessionStore.sessions()), None)

    @staticmethod
    def _named_in(directory: Path, root: Path) -> list[ReviewSession]:
        """The sessions of `root` whose directories are in `directory`, newest first; a
        dot-entry is not one."""
        if not directory.is_dir():
            return []
        names = (
            entry.name
            for entry in directory.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
        return [ReviewSession(root / name) for name in sorted(names, reverse=True)]
