"""The labels file that intake reads for the scope labels it may assign (#1335, #4652)."""

from __future__ import annotations

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
from devops_cli.roadmap.workflow_labels import WORKFLOW_TYPE_LABELS
from tests.support.roadmap_intake import REPO, FakeModel, Recorded, Roadmap, on_github

# ── The labels `.github/labels.yml` declares (#1358) ────────────────────────────

LABELS_RULE = "must declare the scope/* labels intake may assign"


ONLY_SCOPE = "- name: scope/cli\n  color: 'dcdcd6'\n  description: The CLI.\n"


def test_a_run_with_no_candidate_needs_no_labels_file() -> None:
    model = FakeModel()
    plan = Roadmap(labels=None).plan(model)
    assert (plan.decisions, model.embedded, model.requests) == ((), [], [])


@pytest.mark.parametrize(
    ("labels", "names", "ruled"),
    [
        (None, f"{REPO} has no .github/labels.yml at the default branch.", True),
        ("labels: none\n", f"{REPO}'s .github/labels.yml can't be read as label specs", False),
    ],
    ids=["missing", "not-label-specs"],
)
def test_a_labels_file_it_cant_use_stops_intake_before_any_read_or_model_call(
    labels: str | None, names: str, ruled: bool
) -> None:
    """The file is read at the run's first candidate, before its timeline read and the
    embedding call. Its error names the repository the run was given, the file and, for a
    missing file, the rule."""
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


def test_intake_offers_the_package_types_when_the_labels_file_declares_none() -> None:
    """The package declares the `type/*` labels, so a file with only scope labels still gives
    the model every type to pick from, each with its description (#4652)."""
    roadmap = Roadmap(labels=ONLY_SCOPE)
    roadmap.issue("export the board as CSV")
    model = FakeModel()
    roadmap.plan(model)
    assert (
        [request.types for request in model.requests],
        [len(request.type_notes) for request in model.requests],
    ) == ([WORKFLOW_TYPE_LABELS], [len(WORKFLOW_TYPE_LABELS)])


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
