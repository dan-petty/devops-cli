"""The labels that the title of a pull request gives it, added when `devops pr create` opens it
(#2748).

The rule is the one of intake (`roadmap/title_labels.py`). The labels file is the one the
repository holds on the base branch of the pull request, so `--repo` works for any repository.
A label goes on through the issues labels endpoint, which GitHub also uses for pull requests.
"""

from __future__ import annotations

import yaml
from pydantic import ValidationError

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.labels import LabelSpec
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.title_labels import TitleLabels, declared_label_specs, title_labels


def declared_specs(store: roadmap_store.RoadmapStore, *, ref: str | None) -> list[LabelSpec]:
    """The labels that `.github/labels.yml` declares in the repository of `store` on `ref` (the
    default branch when None). A file that is missing, or is no list of label specs, or a read
    that fails, raises `GitHubOperationError` that names the file."""
    text = store.repository_file(CONST_ROADMAP_LABELS_PATH, ref=ref)
    try:
        return declared_label_specs(text)
    except (yaml.YAMLError, ValidationError) as exc:
        raise GitHubOperationError(
            MESSAGES.pr.labels_unreadable.format(
                path=CONST_ROADMAP_LABELS_PATH, error=str(exc)[:200]
            ),
            operation="pr.labels",
            details={"path": CONST_ROADMAP_LABELS_PATH},
        ) from exc


def declared_labels(store: roadmap_store.RoadmapStore, *, ref: str | None) -> tuple[str, ...]:
    """The names of the labels that `.github/labels.yml` declares, with the errors of
    `declared_specs`."""
    return tuple(spec.name for spec in declared_specs(store, ref=ref))


def read_title_labels(repo: str, title: str, *, ref: str | None) -> TitleLabels:
    """The labels that `title` gives, checked against `.github/labels.yml` of `repo` on `ref` (the
    default branch when None). A file that is missing, or is no list of label specs, or a read that
    fails, raises `GitHubOperationError` that names the file."""
    declared = declared_labels(roadmap_store.get_roadmap_store(repo), ref=ref)
    return title_labels(title, declared)


def add_pull_labels(repo: str, pull: int, labels: tuple[str, ...]) -> None:
    """Add each of `labels` to pull request `pull` of `repo`. Every label is tried. When any
    fails, the error names the labels that were not added and the reasons, and the labels that
    were added stay."""
    store = roadmap_store.get_roadmap_store(repo)
    refused: dict[str, str] = {}
    for label in labels:
        try:
            store.label_issue(pull, label)
        except GitHubOperationError as exc:
            refused[label] = str(exc)
    if refused:
        reasons = "; ".join(dict.fromkeys(refused.values()))
        raise GitHubOperationError(
            MESSAGES.pr.labels_refused.format(labels=", ".join(refused), error=reasons),
            operation="pr.labels",
            details={"pull": pull, "labels": ", ".join(refused)[:256]},
        )
