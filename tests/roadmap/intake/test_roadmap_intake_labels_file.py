"""The labels file that intake reads for the type labels it may assign (#1335)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import (
    GitHubOperationError,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake.intake import (
    IntakePlan,
    NewCandidate,
    dry_run_intake,
    plan_intake,
)
from tests.support.roadmap_intake import REPO, FakeModel, Recorded, Roadmap, on_github

# ── The type/* labels `.github/labels.yml` declares (#1358) ─────────────────────

LABELS_RULE = "must declare the type/* labels intake may assign"


ONLY_EPIC = "- name: type/epic\n  color: '5319e7'\n  description: A parent of other items.\n"


def test_a_run_with_no_candidate_needs_no_labels_file() -> None:
    model = FakeModel()
    plan = Roadmap(labels=None).plan(model)
    assert (plan.decisions, model.embedded, model.requests) == ((), [], [])


@pytest.mark.parametrize(
    ("labels", "names", "ruled"),
    [
        (None, f"{REPO} has no .github/labels.yml at the default branch.", True),
        (
            ONLY_EPIC,
            f"{REPO}'s .github/labels.yml at the default branch declares no type/* label",
            True,
        ),
        ("labels: none\n", f"{REPO}'s .github/labels.yml can't be read as label specs", False),
    ],
    ids=["missing", "only-epic", "not-label-specs"],
)
def test_a_labels_file_it_cant_use_stops_intake_before_any_read_or_model_call(
    labels: str | None, names: str, ruled: bool
) -> None:
    """The file is read at the run's first candidate, before its timeline read and the
    embedding call. Its error names the repository the run was given, the file and, for a
    missing or type-less file, the rule."""
    roadmap = Roadmap(labels=labels)
    roadmap.issue("feat: export the board as CSV")
    ran: list[str] = []
    store: Any = Recorded(roadmap.store, ran)
    model = FakeModel()
    with pytest.raises(ConfigurationError) as raised:
        plan_intake(store, repo=REPO, model=model)
    message = str(raised.value)
    assert (
        raised.value.details,
        message.startswith(names),
        LABELS_RULE in message,
        "closures" in ran,
        model.embedded,
        model.requests,
    ) == ({"path": ".github/labels.yml"}, True, ruled, False, [], [])


def test_intake_names_the_repository_whose_labels_file_declares_no_type(
    opened: Roadmap, fake_model: FakeModel, run_intake: Callable[..., str]
) -> None:
    """The command hands the run its `--repo`, so the error names the repository."""
    opened.store.seed_file(".github/labels.yml", ONLY_EPIC)
    opened.issue("feat: export the board as CSV")
    output = run_intake("--plan", exit_code=1)
    assert (
        f"{REPO}'s .github/labels.yml at the default branch declares no type/* label" in output,
        LABELS_RULE in output,
        fake_model.requests,
    ) == (True, True, [])


def test_a_dry_runs_labels_read_waits_for_a_candidate_unless_it_has_a_title() -> None:
    """A run over the open issues reads `.github/labels.yml` only once it has a candidate; a
    `--title` candidate always is one, so its read has no condition."""

    def labels_read(plan: IntakePlan) -> str:
        target = f"repos/{REPO}/contents/.github/labels.yml"
        return next(r.condition for r in plan.requests if r.argv and r.argv[-1] == target)

    every = dry_run_intake(REPO)
    new = dry_run_intake(REPO, new=NewCandidate(title="feat: idea", body="text"))
    assert (labels_read(every), labels_read(new)) == (
        MESSAGES.roadmap.intake_request_conditions["candidate"],
        "",
    )


def test_a_labels_read_github_fails_stays_a_github_error() -> None:
    """Only a missing file is a configuration error: a 502 is GitHub's failure, raised as
    such, still before any model call."""
    github, store = on_github()
    github.files[".github/labels.yml"] = (1, "gh: Server Error (HTTP 502)")
    github.seed_issue(1, "feat: export the board as CSV")
    model = FakeModel()
    with pytest.raises(GitHubOperationError) as raised:
        plan_intake(store, repo=REPO, model=model)
    assert type(raised.value) is GitHubOperationError
    assert "HTTP 502" in str(raised.value)
    assert model.embedded == []
    assert model.requests == []
