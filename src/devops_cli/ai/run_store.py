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
    TEMPLATE_SWEEP = "template-sweep"


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

    def get_by_id(self, run_id: str) -> RunRecord | None:
        """Find a record across all mechanisms in the index."""
        for m in Mechanism:
            record = self.get(m, run_id)
            if record is not None:
                return record
        return None

    def set_baseline(self, mechanism: Mechanism, subject_key: str, run_id: str) -> None:
        """Record the baseline run ID for a subject in Valkey."""
        self._client.set(f"{INDEX_PREFIX}:baseline:{mechanism.value}:{subject_key}", run_id)

    def get_baseline(self, mechanism: Mechanism, subject_key: str) -> str | None:
        """Get the baseline run ID for a subject in Valkey."""
        raw = self._client.get(f"{INDEX_PREFIX}:baseline:{mechanism.value}:{subject_key}")
        return raw.strip() if raw else None


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


def get_run(
    run_id: str, mechanism: Mechanism | None = None, root: Path | None = None
) -> RunRecord | None:
    """Find a run by exact ID or prefix, searching local files then the shared index."""
    base = root or runs_dir()
    pattern = f"{mechanism.value}/{run_id}*.json" if mechanism else f"*/{run_id}*.json"
    matches = sorted(base.glob(pattern), key=lambda p: len(p.stem))
    if matches:
        exact = [p for p in matches if p.stem == run_id]
        chosen = exact[0] if exact else matches[0]
        try:
            return RunRecord.model_validate_json(chosen.read_text(encoding="utf-8"))
        except OSError, ValueError:
            pass

    try:
        with RunIndex.from_settings() as index:
            if mechanism:
                return index.get(mechanism, run_id)
            return index.get_by_id(run_id)
    except RunIndexNotConfiguredError, ValkeyError:
        pass

    return None


class BaselineRecord(BaseModel):
    """The explicit baseline run designated for a subject."""

    mechanism: Mechanism
    subject_key: str
    run_id: str
    set_at: datetime
    subject: dict[str, Any] = Field(default_factory=dict)


def baselines_dir(root: Path | None = None) -> Path:
    """The directory holding baseline run references."""
    return (root or runs_dir()) / "baselines"


def set_baseline(record: RunRecord, root: Path | None = None) -> BaselineRecord:
    """Designate a run as the explicit baseline for its subject."""
    from devops_cli.output.file_writer import write_json_file

    b_record = BaselineRecord(
        mechanism=record.mechanism,
        subject_key=record.subject_key,
        run_id=record.run_id,
        set_at=datetime.now(UTC),
        subject=record.subject,
    )
    path = baselines_dir(root) / record.mechanism.value / f"{record.subject_key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, b_record.model_dump(mode="json"))

    try:
        with RunIndex.from_settings() as index:
            index.set_baseline(record.mechanism, record.subject_key, record.run_id)
    except RunIndexNotConfiguredError, ValkeyError:
        pass

    return b_record


def get_baseline(
    mechanism: Mechanism, subject_key: str, root: Path | None = None
) -> RunRecord | None:
    """Retrieve the baseline RunRecord for a subject, if set."""
    path = baselines_dir(root) / mechanism.value / f"{subject_key}.json"
    if path.exists():
        try:
            b_record = BaselineRecord.model_validate_json(path.read_text(encoding="utf-8"))
            run = get_run(b_record.run_id, mechanism=mechanism, root=root)
            if run is not None:
                return run
        except OSError, ValueError:
            pass

    try:
        with RunIndex.from_settings() as index:
            run_id = index.get_baseline(mechanism, subject_key)
            if run_id:
                return get_run(run_id, mechanism=mechanism, root=root)
    except RunIndexNotConfiguredError, ValkeyError:
        pass

    return None


def list_baselines(root: Path | None = None) -> list[BaselineRecord]:
    """List all configured baselines, newest first."""
    base = baselines_dir(root)
    records = []
    for path in base.glob("*/*.json"):
        try:
            records.append(BaselineRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except OSError, ValueError:
            continue
    return sorted(records, key=lambda b: b.set_at, reverse=True)


def diff_setup(run_a: RunRecord, run_b: RunRecord) -> dict[str, tuple[Any, Any]]:
    """Return keys where setup differs between run_a and run_b."""
    all_keys = sorted(set(run_a.setup) | set(run_b.setup))
    return {
        k: (run_a.setup.get(k), run_b.setup.get(k))
        for k in all_keys
        if run_a.setup.get(k) != run_b.setup.get(k)
    }


def _extract_wall_seconds(results: dict[str, Any]) -> float | None:
    for key in (
        "median_wall_seconds",
        "wall_seconds",
        "total_wall_seconds",
        "duration_seconds",
        "duration",
    ):
        val = results.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _extract_stage_token_sum(stages: list[Any], key: str) -> float | None:
    tokens: list[float] = []
    for s in stages:
        if isinstance(s, dict):
            val = s.get(key)
            if isinstance(val, (int, float)):
                tokens.append(float(val))
    return sum(tokens) if tokens else None


def _extract_prompt_tokens(results: dict[str, Any]) -> float | None:
    stages = results.get("stages")
    if isinstance(stages, list) and stages:
        stage_sum = _extract_stage_token_sum(stages, "median_prompt_tokens")
        if stage_sum is not None:
            return stage_sum
    for key in ("prompt_tokens", "total_prompt_tokens", "total_input_tokens"):
        val = results.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _extract_completion_tokens(results: dict[str, Any]) -> float | None:
    stages = results.get("stages")
    if isinstance(stages, list) and stages:
        stage_sum = _extract_stage_token_sum(stages, "median_completion_tokens")
        if stage_sum is not None:
            return stage_sum
    for key in ("completion_tokens", "total_completion_tokens", "total_output_tokens"):
        val = results.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _extract_recall(results: dict[str, Any]) -> float | None:
    for key in (
        "recall_found",
        "recall_reported",
        "recall",
        "overall_recall",
        "match_rate",
        "agreement_rate",
    ):
        val = results.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _merge_stage_shares(shares: dict[str, float], stage: Any) -> None:
    if not isinstance(stage, dict):
        return
    busy = stage.get("backend_busy_share", {})
    if not isinstance(busy, dict):
        return
    for backend, share in busy.items():
        if isinstance(share, (int, float)):
            shares[str(backend)] = max(shares.get(str(backend), 0.0), float(share))


def _extract_backend_shares(results: dict[str, Any]) -> dict[str, float]:
    shares: dict[str, float] = {}
    stages = results.get("stages")
    if not isinstance(stages, list):
        return shares
    for stage in stages:
        _merge_stage_shares(shares, stage)
    return shares


def extract_metrics(record: RunRecord) -> tuple[dict[str, float], dict[str, float]]:
    """Extract standard metrics and backend busy shares from run results."""
    res = record.results
    metrics: dict[str, float] = {}
    wall = _extract_wall_seconds(res)
    if wall is not None:
        metrics["wall_seconds"] = round(wall, 3)
    p_tokens = _extract_prompt_tokens(res)
    if p_tokens is not None:
        metrics["prompt_tokens"] = round(p_tokens, 1)
    c_tokens = _extract_completion_tokens(res)
    if c_tokens is not None:
        metrics["completion_tokens"] = round(c_tokens, 1)
    recall = _extract_recall(res)
    if recall is not None:
        metrics["recall"] = round(recall, 4)
    calls = res.get("median_llm_calls") or res.get("llm_calls") or res.get("total_calls")
    if isinstance(calls, (int, float)):
        metrics["llm_calls"] = round(float(calls), 1)
    for key in ("total_sites", "parse_failures", "comment_collisions", "tested_mutations"):
        val = res.get(key)
        if isinstance(val, (int, float)):
            metrics[key] = round(float(val), 1)

    return metrics, _extract_backend_shares(res)


class MetricDiff(BaseModel):
    """The difference in one metric between two runs."""

    name: str
    base_value: float
    current_value: float
    absolute_change: float
    percent_change: float | None = None


class RunComparison(BaseModel):
    """Comparison of two runs: setup diff, metrics diff, and backend shares."""

    base_run: RunRecord
    current_run: RunRecord
    same_fingerprint: bool
    setup_diff: dict[str, tuple[Any, Any]]
    metrics: dict[str, MetricDiff]
    backend_shares: dict[str, MetricDiff]


def _calc_metric_diff(name: str, base_val: float, curr_val: float) -> MetricDiff:
    diff = round(curr_val - base_val, 4)
    pct = round((diff / base_val) * 100, 2) if base_val != 0 else None
    return MetricDiff(
        name=name,
        base_value=base_val,
        current_value=curr_val,
        absolute_change=diff,
        percent_change=pct,
    )


def compare_runs(base: RunRecord, current: RunRecord) -> RunComparison:
    """Compare a current run against a base run (or baseline)."""
    setup_diff = diff_setup(base, current)
    base_m, base_backends = extract_metrics(base)
    curr_m, curr_backends = extract_metrics(current)

    metrics = {
        k: _calc_metric_diff(k, base_m.get(k, 0.0), curr_m.get(k, 0.0))
        for k in sorted(set(base_m) | set(curr_m))
    }
    backend_shares = {
        b: _calc_metric_diff(b, base_backends.get(b, 0.0), curr_backends.get(b, 0.0))
        for b in sorted(set(base_backends) | set(curr_backends))
    }
    return RunComparison(
        base_run=base,
        current_run=current,
        same_fingerprint=(base.fingerprint == current.fingerprint),
        setup_diff=setup_diff,
        metrics=metrics,
        backend_shares=backend_shares,
    )


class RegressionTolerances(BaseModel):
    """Allowable regressions before a run check fails."""

    max_recall_drop: float = 0.0
    max_duration_increase: float = 0.15
    max_tokens_increase: float = 0.20


class MetricVerdict(BaseModel):
    """Verification verdict for a single metric against tolerance."""

    metric: str
    base_value: float
    current_value: float
    change_pct: float | None
    tolerance_pct: float
    passed: bool
    reason: str


class RegressionReport(BaseModel):
    """Overall report assessing whether a run regressed past tolerances."""

    passed: bool
    base_run_id: str
    current_run_id: str
    verdicts: list[MetricVerdict]


def _evaluate_recall_verdict(m: MetricDiff, max_drop: float) -> MetricVerdict:
    drop = (m.base_value - m.current_value) / m.base_value if m.base_value > 0 else 0.0
    passed = drop <= max_drop
    reason = (
        f"Recall dropped by {drop:.1%}, exceeds tolerance {max_drop:.1%}"
        if not passed
        else f"Recall within tolerance ({drop:.1%} <= {max_drop:.1%})"
    )
    return MetricVerdict(
        metric="recall",
        base_value=m.base_value,
        current_value=m.current_value,
        change_pct=m.percent_change,
        tolerance_pct=round(max_drop * 100, 2),
        passed=passed,
        reason=reason,
    )


def _evaluate_increase_verdict(
    m: MetricDiff, metric_name: str, max_increase: float
) -> MetricVerdict:
    if m.base_value > 0:
        inc = (m.current_value - m.base_value) / m.base_value
        passed = inc <= max_increase
    else:
        inc = 1.0 if m.current_value > 0.0 else 0.0
        passed = m.current_value <= 0.0
    reason = (
        f"{metric_name} increased by {inc:.1%}, exceeds tolerance {max_increase:.1%}"
        if not passed
        else f"{metric_name} within tolerance ({inc:.1%} <= {max_increase:.1%})"
    )
    return MetricVerdict(
        metric=metric_name,
        base_value=m.base_value,
        current_value=m.current_value,
        change_pct=m.percent_change,
        tolerance_pct=round(max_increase * 100, 2),
        passed=passed,
        reason=reason,
    )


def check_regression(
    comparison: RunComparison, tolerances: RegressionTolerances | None = None
) -> RegressionReport:
    """Check whether current run regressed past configured limits relative to baseline."""
    tol = tolerances or RegressionTolerances()
    verdicts: list[MetricVerdict] = []
    if "recall" in comparison.metrics:
        verdicts.append(_evaluate_recall_verdict(comparison.metrics["recall"], tol.max_recall_drop))
    if "wall_seconds" in comparison.metrics:
        verdicts.append(
            _evaluate_increase_verdict(
                comparison.metrics["wall_seconds"], "wall_seconds", tol.max_duration_increase
            )
        )
    if "prompt_tokens" in comparison.metrics:
        verdicts.append(
            _evaluate_increase_verdict(
                comparison.metrics["prompt_tokens"], "prompt_tokens", tol.max_tokens_increase
            )
        )
    if "parse_failures" in comparison.metrics:
        verdicts.append(
            _evaluate_increase_verdict(comparison.metrics["parse_failures"], "parse_failures", 0.0)
        )
    if "comment_collisions" in comparison.metrics:
        verdicts.append(
            _evaluate_increase_verdict(
                comparison.metrics["comment_collisions"], "comment_collisions", 0.0
            )
        )
    return RegressionReport(
        passed=all(v.passed for v in verdicts),
        base_run_id=comparison.base_run.run_id,
        current_run_id=comparison.current_run.run_id,
        verdicts=verdicts,
    )


__all__ = [
    "INDEX_PREFIX",
    "BaselineRecord",
    "Mechanism",
    "MetricDiff",
    "MetricVerdict",
    "RegressionReport",
    "RegressionTolerances",
    "RunComparison",
    "RunIndex",
    "RunIndexNotConfiguredError",
    "RunRecord",
    "SavedRun",
    "baselines_dir",
    "check_regression",
    "compare_runs",
    "diff_setup",
    "digest",
    "extract_metrics",
    "file_digest",
    "gateway_pool",
    "get_baseline",
    "get_run",
    "keep_runs",
    "list_baselines",
    "load_runs",
    "new_run",
    "record_run",
    "review_setup",
    "runs_dir",
    "save_run",
    "set_baseline",
    "share_runs",
    "source_commit",
]
