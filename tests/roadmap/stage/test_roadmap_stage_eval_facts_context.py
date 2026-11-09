"""The golden set and the facts context of the stage job (#4207).

The stage context holds the failure classes and the runner facts, and the job reads them at the
staged commit. A golden case is frozen at an old commit that can lack the files, so the live run
of the set reads them at the commit of the case and then in the checkout of the run. The run uses
the same builder as the job; the job keeps its loud error when a staged source is missing.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.exceptions import RoadmapStageError
from devops_cli.roadmap.stage.stage import plan_item
from devops_cli.roadmap.stage.stage_context_facts import (
    FAILURE_TAXONOMY_PATH,
    RUNNER_DOCKERFILE_PATH,
    RUNNER_POD_MANIFEST_PATH,
    RUNNER_TOOLS_PATH,
)
from devops_cli.roadmap.stage.stage_eval_cases import (
    CASES_DIRECTORY,
    StageCase,
    cases_with_commit,
    load_cases,
)
from devops_cli.roadmap.stage.stage_eval_run import Outcome, item_of, run_case, run_cases
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import StageRepo

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

_FACT_FILES = (
    FAILURE_TAXONOMY_PATH,
    RUNNER_TOOLS_PATH,
    RUNNER_DOCKERFILE_PATH,
    RUNNER_POD_MANIFEST_PATH,
)
# An issue that cites a failure word and a tool name, so the context holds both fact sections.
_BODY = "The job retries a failed review. Run `devops review` in the runner."
_REASON = "Staged source moved or missing"


def _client(model_fake: ModelFake) -> StageClient:
    from devops_cli.ai.client import get_llm_client

    del model_fake
    return get_llm_client(task="analysis")


def _case(repo: StageRepo, base_commit: str) -> StageCase:
    """A golden case that cites a failure word and a tool, staged on `base_commit`."""
    base = load_cases(REPO_ROOT / CASES_DIRECTORY)[0]
    return base.model_copy(
        update={
            "issue": 1,
            "title": "fix(roadmap): the job retries a failed review",
            "issue_body": _BODY,
            "base_commit": base_commit,
            "defects": (),
        }
    )


def _text_of(paths: tuple[str, ...]) -> dict[str, str]:
    """The text of the real files `paths` of this repository."""
    return {path: (REPO_ROOT / path).read_text(encoding="utf-8") for path in paths}


def _stage(
    repo: StageRepo, *, absent_at_commit: tuple[str, ...], absent_at_head: tuple[str, ...] = ()
) -> str:
    """Commits the fact files that are not in `absent_at_commit`, and returns that commit. Then
    commits the files that are in `absent_at_commit` and not in `absent_at_head`, so the head of
    the repository holds them and the returned commit does not."""
    first = tuple(path for path in _FACT_FILES if path not in absent_at_commit)
    if first:
        repo.track(_text_of(first))
    old = repo.git("rev-parse", "HEAD")
    later = tuple(path for path in absent_at_commit if path not in absent_at_head)
    if later:
        repo.track(_text_of(later))
    return old


@pytest.mark.parametrize(
    "absent_at_commit",
    [
        pytest.param((FAILURE_TAXONOMY_PATH, RUNNER_TOOLS_PATH), id="failure-and-runner-tools"),
        pytest.param((RUNNER_TOOLS_PATH,), id="runner-tools"),
        pytest.param((FAILURE_TAXONOMY_PATH,), id="failure"),
    ],
)
def test_a_case_whose_commit_lacks_fact_files_reads_them_in_the_checkout_and_reaches_the_model(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    absent_at_commit: tuple[str, ...],
) -> None:
    """The commit of the case lacks files that the head of the repository holds. The case reads
    them there and reaches the model: the three shapes of the 42 refused cases (#4207)."""
    old = _stage(stage_repo, absent_at_commit=absent_at_commit)
    case = _case(stage_repo, old)
    model_fake.answer(AIClientError("the model is down"))

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, run.reason, model_fake.call_count) == (Outcome.FAILED, "AIClientError", 1)


def test_a_fact_file_that_the_checkout_lacks_too_still_ends_the_case_refused_with_its_path(
    stage_repo: StageRepo, model_fake: ModelFake, openspec_fake: OpenSpecFake
) -> None:
    """The fallback is the checkout of the run. A file that neither the commit nor the checkout
    holds is a moved source, and the case ends `refused` with the path, as in the job."""
    old = _stage(
        stage_repo,
        absent_at_commit=(RUNNER_TOOLS_PATH,),
        absent_at_head=(RUNNER_TOOLS_PATH,),
    )
    case = _case(stage_repo, old)
    model_fake.answer(AIClientError("the model is down"))

    run = run_case(case, _client(model_fake), stage_repo.clone)

    assert (run.outcome, model_fake.call_count) == (Outcome.REFUSED, 0)
    assert f"{_REASON}: {RUNNER_TOOLS_PATH}" in run.reason


def test_the_job_still_raises_when_a_fact_file_is_absent_at_the_staged_commit(
    stage_repo: StageRepo, model_fake: ModelFake, openspec_fake: OpenSpecFake
) -> None:
    """The job reads the staged commit only. It never falls back to a checkout, so a source that
    moved fails the item loudly (#3258)."""
    old = _stage(stage_repo, absent_at_commit=(FAILURE_TAXONOMY_PATH,))
    case = _case(stage_repo, old)
    stage_repo.git("switch", "-q", "--detach", old)

    with pytest.raises(RoadmapStageError, match=_REASON):
        plan_item(
            item_of(case),
            client=_client(model_fake),
            checkout=stage_repo.clone,
            sha=old,
        )

    assert model_fake.call_count == 0


def _holds(commit: str, path: str) -> bool:
    """Whether `commit` of this checkout holds `path`. A shallow clone lacks the old commits."""
    found = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{commit}:{path}"],
        check=False,
        capture_output=True,
    )
    return found.returncode == 0


def _one_case_of_each_missing_shape(cases: list[StageCase]) -> list[StageCase]:
    """The first golden case for each way a commit lacks the fact files: it lacks both
    `failure.py` and `runner_tools.py`, only `runner_tools.py`, or only `failure.py`. A run of one
    case reads the whole tree, so the test runs one case of each shape and not all 48."""
    shapes: dict[tuple[bool, bool], StageCase] = {}
    for case in cases:
        has_failure = _holds(case.base_commit, FAILURE_TAXONOMY_PATH)
        has_tools = _holds(case.base_commit, RUNNER_TOOLS_PATH)
        if not (has_failure and has_tools):
            shapes.setdefault((has_failure, has_tools), case)
    return list(shapes.values())


def test_a_golden_case_of_each_missing_shape_reaches_the_model_and_none_ends_refused(
    model_fake: ModelFake, openspec_fake: OpenSpecFake
) -> None:
    """42 of the 48 cases ended `refused` before a model call, because the files of the facts
    context are newer than their commits (#4207). The 42 fall in three shapes; one case of each
    shape reaches the model. The test needs the old commits, so a shallow clone skips it."""
    cases, _ = cases_with_commit(load_cases(REPO_ROOT / CASES_DIRECTORY))
    probe = [case for case in cases if _holds(case.base_commit, "CONTEXT.md")]
    chosen = _one_case_of_each_missing_shape(probe)
    if not chosen:
        pytest.skip("this clone holds no old commit of the golden set")
    model_fake.answer(AIClientError("the model is down"))

    runs = run_cases(chosen, _client(model_fake), REPO_ROOT)

    assert [(run.name, run.outcome, run.reason) for run in runs] == [
        (case.name, Outcome.FAILED, "AIClientError") for case in chosen
    ]
    assert model_fake.call_count == len(chosen)
