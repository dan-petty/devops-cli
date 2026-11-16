"""Tests for retrying a refused pull request body in the implement job (#3599)."""

from __future__ import annotations

import subprocess
from typing import Any

from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement_run import apply_implement
from devops_cli.roadmap.pull_form import body_problems
from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import WINDOW, command_text
from tests.support.roadmap_implement import (
    PULL,
    JobWorld,
    archive_effect,
    two_groups,
)


def _rewrite_why(job_world: JobWorld, why: str) -> None:
    """Make the archive step leave `why` as the "Why" of the archived proposal."""

    def archive_with_why(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        done = archive_effect(call)
        assert call.cwd is not None
        change = command_text(call).split()[-1]
        proposal = call.cwd / "openspec/changes/archive" / f"2026-10-29-{change}" / "proposal.md"
        text = proposal.read_text(encoding="utf-8")
        proposal.write_text(
            text.replace("The job drops the last comment of a thread (#1). It must keep it.", why),
            encoding="utf-8",
        )
        return done

    job_world.programs.answer(
        lambda call: command_text(call).startswith("uv run devops openspec archive"),
        ProcessAnswer(side_effect=archive_with_why),
    )


def test_a_refused_body_is_rebuilt_once_and_written(job_world: JobWorld) -> None:
    _rewrite_why(job_world, "The job drops the last comment of a thread (#1)...")
    calls: list[tuple[str, list[str]]] = []

    def fake_rewriter(text: str, problems: Any) -> str:
        calls.append((text, list(problems)))
        return "The job drops the last comment of a thread (#1). It must keep it."

    applied = apply_implement(
        job_world.store,
        job_world.plan(),
        source=job_world.repo.clone,
        model=two_groups().model(),
        window=WINDOW,
        rewriter=fake_rewriter,
    )

    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert len(calls) == 1
    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert body_problems(patched["body"]) == []
    assert "The job drops the last comment of a thread (#1). It must keep it." in patched["body"]


def test_a_second_refusal_stops_the_item_as_refused_reply(job_world: JobWorld) -> None:
    _rewrite_why(job_world, "The job drops the last comment of a thread (#1)...")
    calls: list[tuple[str, list[str]]] = []

    def fake_rewriter(text: str, problems: Any) -> str:
        calls.append((text, list(problems)))
        return "Still a bad why that ends with a cut mark..."

    applied = apply_implement(
        job_world.store,
        job_world.plan(),
        source=job_world.repo.clone,
        model=two_groups().model(),
        window=WINDOW,
        rewriter=fake_rewriter,
    )

    assert (applied.ready, applied.stopped, applied.failed) == ((), (1,), ())
    assert len(calls) == 1
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    item = job_world.store.item(1)
    assert item is not None
    assert item.job_record.get(ImplementRecordKey.FAILURE) == FailureClass.REFUSED_REPLY.value


def test_a_cut_why_in_the_rebuilt_text_stops_the_item(job_world: JobWorld) -> None:
    _rewrite_why(job_world, "The job drops the last comment of a thread (#1)...")
    calls: list[str] = []

    def fake_rewriter(text: str, problems: Any) -> str:
        calls.append(text)
        return "A second text that ends with cut..."

    applied = apply_implement(
        job_world.store,
        job_world.plan(),
        source=job_world.repo.clone,
        model=two_groups().model(),
        window=WINDOW,
        rewriter=fake_rewriter,
    )

    assert applied.stopped == (1,)
    assert len(calls) == 1
    assert job_world.sent("PATCH", f"pulls/{PULL}") == []
    item = job_world.store.item(1)
    assert item is not None
    assert item.job_record.get(ImplementRecordKey.FAILURE) == FailureClass.REFUSED_REPLY.value
