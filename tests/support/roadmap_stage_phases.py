"""The run folder of the stage Job on its phases, for the tests of `publish` (#6705).

`prepare_run` runs `prepare` on a stage repository, which the gate of OpenSpec reads as sound: a
`package-lock.json` that pins the OpenSpec of the fake. `hand_over` writes the outputs of an agent
phase in `out/`, as a stub agent leaves them: the patch of the files that it gives, made from the
base with `git diff` in the clone of `prepare`, the body candidate and the outcome.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME,
    CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE,
    CONST_ROADMAP_STAGE_PLAN_PATCH_FILE,
)
from devops_cli.roadmap.phases.files import RunFolders
from devops_cli.roadmap.stage.stage_change import StageProposal, render_change
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO, StageRepo, run_git, seed_stageable

PHASE_CHANGE = "1-the-job-drops-a-comment"
PHASE_ROOT = f"openspec/changes/{PHASE_CHANGE}"
# The key of OpenSpec in the `packages` of a `package-lock.json`.
_LOCK_KEY = "node_modules/@fission-ai/openspec"


def lockfile(version: str) -> str:
    """A `package-lock.json` that pins OpenSpec at `version`."""
    return json.dumps({"lockfileVersion": 3, "packages": {_LOCK_KEY: {"version": version}}})


def gate_files(version: str) -> dict[str, str]:
    """The files that the gate of OpenSpec reads as sound in a stage repository, with OpenSpec
    pinned at `version`: the generated skills that the repository commits, and the lockfile."""
    from devops_cli.openspec.skills import generated_files
    from tests.support.paths import REPO_ROOT

    skills = {path: content.decode("utf-8") for path, content in generated_files(REPO_ROOT).items()}
    return {**skills, "package-lock.json": lockfile(version)}


def plan_files(
    created: date, proposal: StageProposal | None = None, change: str = PHASE_CHANGE
) -> dict[str, str]:
    """The files of the change folder of the stock plan, dated `created`."""
    return render_change(
        change, proposal or make_stage_proposal(), {"comment-thread"}, created=created
    )


def prepare_run(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    tmp_path: Path,
    *,
    now: datetime | None,
    body: str = "The job drops the last comment of a thread.",
) -> tuple[RunFolders, int]:
    """The run folder that `prepare` handed to the agent phase, and the number of the item."""
    from devops_cli.roadmap.stage.stage_job_phases import prepare_stage_job

    folders = RunFolders(tmp_path / "run").make()
    number = seed_stageable(store, body=body)
    run = prepare_stage_job(
        store, folders, repo=STAGE_REPO, item=number, source=repo.clone, now=now
    )
    assert run is None
    return folders, number


def agent_clone(folders: RunFolders) -> Path:
    """The clone of the agent phase of the run."""
    return folders.work / CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME


def hand_over(
    folders: RunFolders,
    files: Mapping[str, str | bytes | None],
    *,
    outcome: Mapping[str, Any] | None = None,
    candidate: str | None = None,
    links: Mapping[str, str] | None = None,
    modes: Mapping[str, int] | None = None,
) -> bytes:
    """Write the outputs of a stub agent phase and give the patch: `files` (text, bytes, or None
    for a removal) in the clone of `prepare`, each link of `links` and each mode of `modes`, as a
    patch from the base; the body candidate; and `outcome` (`{"end": "ended"}` by default)."""
    clone = agent_clone(folders)
    base = run_git(clone, "rev-parse", "HEAD^")
    changed = [*files, *(links or {}), *(modes or {})]
    for path, text in files.items():
        target = clone / path
        if text is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            target.write_bytes(text)
        else:
            target.write_text(text, encoding="utf-8")
    for path, pointed in (links or {}).items():
        (clone / path).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(pointed, clone / path)
    for path, mode in (modes or {}).items():
        (clone / path).chmod(mode)
    run_git(clone, "add", "-A", "--", PHASE_ROOT, *changed)
    folders.out.mkdir(mode=0o700, exist_ok=True)
    patch = folders.out / CONST_ROADMAP_STAGE_PLAN_PATCH_FILE
    run_git(
        clone,
        "diff",
        "--binary",
        "--full-index",
        "--cached",
        f"--output={patch}",
        base,
        "--",
        PHASE_ROOT,
        *changed,
    )
    if candidate is not None:
        (folders.out / CONST_ROADMAP_STAGE_CANDIDATE_OUT_FILE).write_text(
            candidate, encoding="utf-8"
        )
    (folders.out / CONST_ROADMAP_PHASE_OUTCOME_FILE).write_text(
        json.dumps(dict(outcome or {"end": "ended"})), encoding="utf-8"
    )
    return patch.read_bytes()


__all__ = [
    "PHASE_CHANGE",
    "PHASE_ROOT",
    "agent_clone",
    "gate_files",
    "hand_over",
    "lockfile",
    "plan_files",
    "prepare_run",
]
