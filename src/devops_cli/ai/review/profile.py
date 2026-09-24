"""Where a review's time goes: wall time, LLM calls, tokens and serving backends per stage.

A review is a pipeline of stages (payloads, persona review, verification, reranking, report).
Without a breakdown, a change to gateway weights or models could only be judged by total wall
time, which also moves with the number of candidate findings a run happens to produce. A profile
records each stage and every LLM call made during it, and is written next to the session's
findings as `profile.json`.

Calls are observed through the spend ledger, the one place every LLM call passes through with its
tokens and the backend the gateway routed it to. The current stage travels in a context variable,
which asyncio tasks and `asyncio.to_thread` copy into the review's worker threads. Each stage also
has a `review.*` trace span, and the profile's session ID is an attribute of the session's span.

`devops ai review benchmark` reviews the same files several times, collects each run's profile and
summarises them by their medians, since the findings of identical runs vary.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.spend.ledger import observe_llm_calls

PROFILE_FILENAME = "profile.json"
BENCHMARKS_DIRNAME = "benchmarks"

_ACTIVE: ContextVar[ReviewProfiler | None] = ContextVar("review_profiler", default=None)
_STAGE: ContextVar[str | None] = ContextVar("review_stage", default=None)
_COLLECTED: ContextVar[list[ReviewProfile] | None] = ContextVar("review_profiles", default=None)


class StageProfile(BaseModel):
    """One stage of a review."""

    name: str
    wall_seconds: float = 0.0
    llm_calls: int = 0
    cached_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    backends: dict[str, int] = Field(default_factory=dict)


class ReviewProfile(BaseModel):
    """A review's stages, LLM usage and findings."""

    session_id: str
    target: str
    files: int = 0
    total_wall_seconds: float = 0.0
    llm_calls: int = 0
    cached_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    candidate_findings: int = 0
    verified_findings: int = 0
    reported_findings: int = 0
    # How each static analyzer took part: ran, built-in patterns, not installed or no files. A
    # scan that found nothing is clean only for the analyzers that ran.
    static_analyzers: dict[str, str] = Field(default_factory=dict)
    stages: list[StageProfile] = Field(default_factory=list)

    @property
    def seconds_per_candidate(self) -> float | None:
        """Wall time per candidate finding, which scales with verification work."""
        if not self.candidate_findings:
            return None
        return self.total_wall_seconds / self.candidate_findings

    def write(self, session_dir: Path) -> Path:
        """Write the profile into the review session directory."""
        path = session_dir / PROFILE_FILENAME
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, session_dir: Path) -> ReviewProfile | None:
        """The session's profile; None when it has none or it cannot be read."""
        try:
            return cls.model_validate_json((session_dir / PROFILE_FILENAME).read_text("utf-8"))
        except OSError, ValueError:
            return None


class ReviewProfiler:
    """Collects stage timings and the LLM calls made during each stage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._stages: dict[str, StageProfile] = {}
        self._findings = (0, 0, 0)
        self._static_analyzers: dict[str, str] = {}

    def observe(self, call: dict[str, Any]) -> None:
        """Credit an LLM call to the stage running in the caller's context.

        A reply served from the response cache is counted apart: no backend did any work for it.
        """
        name = _STAGE.get() or "unstaged"
        with self._lock:
            stage = self._stages.setdefault(name, StageProfile(name=name))
            if call.get("cached"):
                stage.cached_calls += 1
                return
            stage.llm_calls += 1
            stage.prompt_tokens += int(call.get("prompt_tokens") or 0)
            stage.completion_tokens += int(call.get("completion_tokens") or 0)
            served_by = call.get("served_by")
            if served_by:
                stage.backends[served_by] = stage.backends.get(served_by, 0) + 1

    def add_stage_time(self, name: str, seconds: float) -> None:
        with self._lock:
            stage = self._stages.setdefault(name, StageProfile(name=name))
            stage.wall_seconds += seconds

    def set_findings(self, *, candidates: int, verified: int, reported: int) -> None:
        self._findings = (candidates, verified, reported)

    def set_static_analyzers(self, states: dict[str, str]) -> None:
        self._static_analyzers = dict(states)

    def build(self, *, session_id: str, target: str, files: int = 0) -> ReviewProfile:
        """Assemble the profile of everything recorded so far."""
        with self._lock:
            stages = [s.model_copy(deep=True) for s in self._stages.values()]
        for stage in stages:
            stage.wall_seconds = round(stage.wall_seconds, 3)
        candidates, verified, reported = self._findings
        return ReviewProfile(
            session_id=session_id,
            target=target,
            files=files,
            total_wall_seconds=round(time.monotonic() - self._started, 3),
            llm_calls=sum(s.llm_calls for s in stages),
            cached_calls=sum(s.cached_calls for s in stages),
            prompt_tokens=sum(s.prompt_tokens for s in stages),
            completion_tokens=sum(s.completion_tokens for s in stages),
            candidate_findings=candidates,
            verified_findings=verified,
            reported_findings=reported,
            static_analyzers=dict(self._static_analyzers),
            stages=stages,
        )


def active_profiler() -> ReviewProfiler | None:
    """The profiler of the review running in this context, if any."""
    return _ACTIVE.get()


@contextmanager
def profiling() -> Iterator[ReviewProfiler]:
    """Profile the review run inside the block."""
    profiler = ReviewProfiler()
    token = _ACTIVE.set(profiler)
    try:
        with observe_llm_calls(profiler.observe):
            yield profiler
    finally:
        _ACTIVE.reset(token)


@contextmanager
def collect_profiles() -> Iterator[list[ReviewProfile]]:
    """Collect the profile of every review completed inside the block."""
    profiles: list[ReviewProfile] = []
    token = _COLLECTED.set(profiles)
    try:
        yield profiles
    finally:
        _COLLECTED.reset(token)


def report_profile(profile: ReviewProfile) -> None:
    """Hand a completed review's profile to the benchmark collecting profiles, if any."""
    collected = _COLLECTED.get()
    if collected is not None:
        collected.append(profile)


@contextmanager
def review_stage(name: str) -> Iterator[None]:
    """Mark a review stage; a no-op unless a review is being profiled."""
    profiler = _ACTIVE.get()
    if profiler is None:
        yield
        return
    token = _STAGE.set(name)
    started = time.monotonic()
    try:
        yield
    finally:
        _STAGE.reset(token)
        profiler.add_stage_time(name, time.monotonic() - started)


class StageSummary(BaseModel):
    """Medians of one stage across benchmark runs."""

    name: str
    median_wall_seconds: float
    median_llm_calls: float
    median_prompt_tokens: float
    median_completion_tokens: float
    backends: dict[str, int] = Field(default_factory=dict)


class BenchmarkSummary(BaseModel):
    """Medians across repeated reviews of the same target."""

    target: str = ""
    files: int = 0
    corpus_digest: str = ""
    created_at: str = ""
    runs: int
    median_wall_seconds: float
    median_llm_calls: float
    median_candidate_findings: float
    median_reported_findings: float
    median_seconds_per_candidate: float | None = None
    # Every state each static analyzer had across the runs; runs that differ show more than one.
    static_analyzers: dict[str, list[str]] = Field(default_factory=dict)
    stages: list[StageSummary] = Field(default_factory=list)
    sessions: list[str] = Field(default_factory=list)

    def write(self, reviews_dir: Path) -> Path:
        """Save the summary under the reviews directory, one file per benchmark."""
        directory = reviews_dir / BENCHMARKS_DIRNAME
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromisoformat(self.created_at) if self.created_at else datetime.now(UTC)
        path = directory / f"{stamp.strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def _median(values: list[float]) -> float:
    return round(float(statistics.median(values)), 3) if values else 0.0


def _analyzer_states_across(profiles: list[ReviewProfile]) -> dict[str, list[str]]:
    """The states each static analyzer had across runs, in the order they first appeared."""
    states: dict[str, list[str]] = {}
    for profile in profiles:
        for name, state in profile.static_analyzers.items():
            if state not in states.setdefault(name, []):
                states[name].append(state)
    return states


def summarize_profiles(profiles: list[ReviewProfile]) -> BenchmarkSummary:
    """Summarise repeated reviews by their medians; single runs of a review are noisy."""
    per_candidate = [p.seconds_per_candidate for p in profiles if p.seconds_per_candidate]
    names = list(dict.fromkeys(s.name for p in profiles for s in p.stages))
    stages: list[StageSummary] = []
    for name in names:
        runs = [s for p in profiles for s in p.stages if s.name == name]
        backends: Counter[str] = Counter()
        for stage in runs:
            backends.update(stage.backends)
        stages.append(
            StageSummary(
                name=name,
                median_wall_seconds=_median([s.wall_seconds for s in runs]),
                median_llm_calls=_median([float(s.llm_calls) for s in runs]),
                median_prompt_tokens=_median([float(s.prompt_tokens) for s in runs]),
                median_completion_tokens=_median([float(s.completion_tokens) for s in runs]),
                backends=dict(backends),
            )
        )
    return BenchmarkSummary(
        target=profiles[0].target if profiles else "",
        files=profiles[0].files if profiles else 0,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        runs=len(profiles),
        median_wall_seconds=_median([p.total_wall_seconds for p in profiles]),
        median_llm_calls=_median([float(p.llm_calls) for p in profiles]),
        median_candidate_findings=_median([float(p.candidate_findings) for p in profiles]),
        median_reported_findings=_median([float(p.reported_findings) for p in profiles]),
        median_seconds_per_candidate=_median(per_candidate) if per_candidate else None,
        static_analyzers=_analyzer_states_across(profiles),
        stages=stages,
        sessions=[p.session_id for p in profiles],
    )


__all__ = [
    "BENCHMARKS_DIRNAME",
    "PROFILE_FILENAME",
    "BenchmarkSummary",
    "ReviewProfile",
    "ReviewProfiler",
    "StageProfile",
    "StageSummary",
    "active_profiler",
    "collect_profiles",
    "profiling",
    "report_profile",
    "review_stage",
    "summarize_profiles",
]
