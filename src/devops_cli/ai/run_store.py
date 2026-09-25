"""The evaluation run store: every benchmark and evaluation run, kept and shared (#554).

Benchmarks and evaluations are repeated over the life of the tool, so each run is kept as one
record: the mechanism that ran, its subject, its setup and what it measured. The data directory
is the source of truth, one JSON file per run under `<runs dir>/<mechanism>/`. Each record is
mirrored to Valkey, an index every workstation shares. `devops ai runs reindex` rebuilds the index
from the files, and every mechanism works without Valkey.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, Field, computed_field

from devops_cli.config.constants import (
    CONST_AI_GATEWAY_PROVIDER,
    CONST_CACHE_NAMESPACE_ROOT,
    CONST_RUNS_DIR_NAME,
)
from devops_cli.config.defaults import DEFAULT_RUNS_INDEX_TIMEOUT_SECONDS
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.valkey.client import ValkeyClient

if TYPE_CHECKING:
    from devops_cli.config.settings import AIConfig

INDEX_PREFIX = f"{CONST_CACHE_NAMESPACE_ROOT}:runs"


class Mechanism(StrEnum):
    """What produced a run."""

    REVIEW_BENCHMARK = "review-benchmark"
    SAMPLE_VALIDATION = "sample-validation"
    CORPUS_SCORE = "corpus-score"
    GATEWAY_TUNE = "gateway-tune"
    PROMPT_EVAL = "prompt-eval"
    AI_BENCHMARK = "ai-benchmark"


def digest(value: Any) -> str:
    """A short digest of JSON data that depends on its content, not its key order."""
    text = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def file_digest(path: Path) -> str | None:
    """A short digest of a file's bytes, or None when it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


class RunRecord(BaseModel):
    """One run of a benchmark or evaluation."""

    mechanism: Mechanism
    run_id: str
    created_at: datetime
    version: str
    # The devops-cli commit, marked `-dirty` when its source had uncommitted changes.
    commit: str | None = None
    # What could change the result: models, backends and weights, page size, personas.
    setup: dict[str, Any] = Field(default_factory=dict)
    # What was measured: a corpus digest, sample commits, a target.
    subject: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        """Equal for runs with the same setup."""
        return digest(self.setup)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subject_key(self) -> str:
        """Equal for runs of the same subject."""
        return digest(self.subject)


def source_commit() -> str | None:
    """The commit of the checkout devops-cli runs from, or None when it is installed."""
    from devops_cli.core.process import run_subprocess

    package = Path(__file__).resolve().parents[1]

    def git(*args: str) -> str | None:
        result = run_subprocess(["git", "-C", str(package), *args], quiet=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None

    top = git("rev-parse", "--show-toplevel")
    # An installed package may sit inside some other repository, such as a project's .venv.
    if top is None or Path(top).resolve() / "src" / package.name != package:
        return None
    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--untracked-files=no", "--", "src")
    return f"{commit}-dirty" if commit and dirty else commit


def gateway_pool(task: AIConfig) -> list[dict[str, Any]] | None:
    """The gateway's deployments of a task's model group and their weights; None when unknown."""
    from devops_cli.ai.client import AICredentialsError
    from devops_cli.ai.gateway import fetch_model_info
    from devops_cli.ai.gateway_tune import backend_label, discover_pool
    from devops_cli.config.settings import get_ai_api_key, load_settings

    try:
        info = fetch_model_info(
            task.gateway_url, task.allow_private_network, get_ai_api_key(load_settings())
        )
    except AICredentialsError:
        return None
    pool = [
        {
            "backend": backend_label(d["api_base"]),
            "model": d["model"],
            "weight": d["weight"],
            "max_input_tokens": d["max_input_tokens"],
        }
        for d in discover_pool(info or [], task.model)
    ]
    return sorted(pool, key=lambda d: (d["backend"], d["model"])) or None


def review_setup(**extra: Any) -> dict[str, Any]:
    """What a review's results depend on: its models, the gateway's pool and the page size."""
    from devops_cli.ai.review.chunker import review_page_chars
    from devops_cli.config.settings import load_settings

    ai = load_settings().ai
    tasks = {"analysis": ai.for_task("analysis"), "verification": ai.for_task("verification")}
    setup: dict[str, Any] = {
        "models": {name: f"{t.provider}/{t.model}" for name, t in tasks.items()},
        "page_chars": review_page_chars(tasks["analysis"].context_window),
    }
    gateway_tasks = {t.model: t for t in tasks.values() if t.provider == CONST_AI_GATEWAY_PROVIDER}
    if gateway_tasks:
        setup["pools"] = {group: gateway_pool(t) for group, t in sorted(gateway_tasks.items())}
    return setup | extra


def new_run(
    mechanism: Mechanism,
    *,
    setup: dict[str, Any],
    subject: dict[str, Any],
    results: dict[str, Any],
) -> RunRecord:
    """A record of a run that just finished, stamped with the devops-cli version and commit."""
    from devops_cli import __version__

    created_at = datetime.now(UTC)
    return RunRecord(
        mechanism=mechanism,
        run_id=f"{created_at:%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}",
        created_at=created_at,
        version=__version__,
        commit=source_commit(),
        setup=setup,
        subject=subject,
        results=results,
    )


def runs_dir() -> Path:
    """The directory run records are kept in, one subdirectory per mechanism."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    directory = (
        Path(env_data_dir) / CONST_RUNS_DIR_NAME if env_data_dir else load_settings().data.runs_dir
    )
    return resolve_data_path(directory)


def save_run(record: RunRecord, root: Path | None = None) -> Path:
    """Write a record to the data directory, atomically."""
    from devops_cli.output.file_writer import write_json_file

    path = (root or runs_dir()) / record.mechanism.value / f"{record.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json_file(path, record.model_dump(mode="json"))


def load_runs(mechanism: Mechanism | None = None, root: Path | None = None) -> list[RunRecord]:
    """Every record in the data directory, oldest first; unreadable files are skipped."""
    base = root or runs_dir()
    pattern = f"{mechanism.value}/*.json" if mechanism else "*/*.json"
    records = []
    for path in base.glob(pattern):
        try:
            records.append(RunRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except OSError, ValueError:
            continue
    return sorted(records, key=lambda r: (r.created_at, r.run_id))


class RunIndexNotConfiguredError(DevOpsCLIError):
    """No shared run index is configured."""


class RunIndex:
    """The shared index in Valkey: each record, and its run ids by mechanism and by subject."""

    def __init__(self, client: ValkeyClient) -> None:
        self._client = client

    @classmethod
    def connect(cls, url: str, password: str | None) -> RunIndex:
        """The index in the Valkey at `url`, such as `valkey://host:port`."""
        return cls(
            ValkeyClient(host=url, password=password, timeout=DEFAULT_RUNS_INDEX_TIMEOUT_SECONDS)
        )

    @classmethod
    def from_settings(cls) -> RunIndex:
        """The index at `runs.index_url`."""
        from devops_cli.config.settings import get_runs_index_password, load_settings

        settings = load_settings()
        if not settings.runs.index_url:
            raise RunIndexNotConfiguredError(
                "no run index is configured; `devops ai runs connect` sets one up"
            )
        return cls.connect(settings.runs.index_url, get_runs_index_password(settings))

    @property
    def location(self) -> str:
        """Where the index is, for messages."""
        return f"{self._client.host}:{self._client.port}"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._client.close()

    @staticmethod
    def _commands(record: RunRecord) -> list[list[Any]]:
        mechanism, score = record.mechanism.value, record.created_at.timestamp()
        return [
            ["SET", f"{INDEX_PREFIX}:record:{mechanism}:{record.run_id}", record.model_dump_json()],
            ["ZADD", f"{INDEX_PREFIX}:mechanism:{mechanism}", score, record.run_id],
            [
                "ZADD",
                f"{INDEX_PREFIX}:subject:{mechanism}:{record.subject_key}",
                score,
                record.run_id,
            ],
        ]

    def ping(self) -> bool:
        """Whether the index answers."""
        return self._client.ping()

    def put(self, *records: RunRecord) -> int:
        """Add or replace records in the index, in one round trip; the number added."""
        self._client.pipeline([command for r in records for command in self._commands(r)])
        return len(records)

    def run_ids(self, mechanism: Mechanism) -> list[str]:
        """Every indexed run of a mechanism, from any workstation, oldest first."""
        ids = self._client.execute("ZRANGE", f"{INDEX_PREFIX}:mechanism:{mechanism.value}", 0, -1)
        return [str(i) for i in ids or []]

    def get(self, mechanism: Mechanism, run_id: str) -> RunRecord | None:
        """An indexed record, or None."""
        raw = self._client.get(f"{INDEX_PREFIX}:record:{mechanism.value}:{run_id}")
        return RunRecord.model_validate_json(raw) if raw else None


@dataclass(frozen=True)
class SavedRun:
    """A record kept in the data directory, and whether it reached the shared index."""

    record: RunRecord
    path: Path
    shared: bool
    # Where the index is when shared; why not when it is not.
    detail: str


def share_runs(*records: RunRecord) -> tuple[bool, str]:
    """Mirror records to the shared index, reporting rather than raising when it is unreachable."""
    from devops_cli.security.sanitizer import mask_secrets

    try:
        with RunIndex.from_settings() as index:
            index.put(*records)
            return True, index.location
    except RunIndexNotConfiguredError as exc:
        return False, exc.message
    except ValkeyError as exc:
        return False, (
            f"the run index is unreachable ({mask_secrets(exc.message)}); "
            "`devops ai runs reindex` shares it later"
        )


def keep_runs(records: list[RunRecord]) -> list[SavedRun]:
    """Save records to the data directory, then share them all in one round trip."""
    paths = [save_run(record) for record in records]
    shared, detail = share_runs(*records) if records else (False, "no runs")
    return [SavedRun(r, path, shared, detail) for r, path in zip(records, paths, strict=True)]


def record_run(
    mechanism: Mechanism,
    *,
    setup: dict[str, Any],
    subject: dict[str, Any],
    results: dict[str, Any],
) -> SavedRun:
    """Keep a finished run in the data directory and share it through the index."""
    return keep_runs([new_run(mechanism, setup=setup, subject=subject, results=results)])[0]


__all__ = [
    "INDEX_PREFIX",
    "Mechanism",
    "RunIndex",
    "RunIndexNotConfiguredError",
    "RunRecord",
    "SavedRun",
    "digest",
    "file_digest",
    "gateway_pool",
    "keep_runs",
    "load_runs",
    "new_run",
    "record_run",
    "review_setup",
    "runs_dir",
    "save_run",
    "share_runs",
    "source_commit",
]
