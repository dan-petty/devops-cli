"""The labels that the Conventional Commit title of an issue or a pull request gives (#2715, #2748).

Intake gives an issue its labels with this rule, and `devops pr create` gives a pull request the
same labels. The type of the title gives the `type/*` label (`CONST_ROADMAP_COMMIT_TYPE_LABELS`
maps each type) and its scope gives `scope/<scope>`. A label that `.github/labels.yml` does not
declare is never given, and a scope with no declared label is reported, not hidden.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

import yaml
from pydantic import TypeAdapter

from devops_cli.config.constants import (
    CONST_ROADMAP_COMMIT_TYPE_LABELS,
    CONST_ROADMAP_SCOPE_LABEL_PREFIX,
)
from devops_cli.github.labels import LabelSpec
from devops_cli.roadmap.commit_title import commit_scope, commit_type

_LABEL_SPECS = TypeAdapter(list[LabelSpec])


@dataclass(frozen=True)
class TitleLabels:
    """The labels a title gives: its declared `type/*` label and `scope/*` label, and the scope
    label that the file does not declare, which the title asked for."""

    type_label: str | None = None
    scope_label: str | None = None
    undeclared_scope: str | None = None

    @property
    def labels(self) -> tuple[str, ...]:
        """The labels to add: the type label, then the scope label, each when the title gives it."""
        return tuple(label for label in (self.type_label, self.scope_label) if label)


def declared_label_specs(text: str) -> list[LabelSpec]:
    """The labels that the text of `.github/labels.yml` declares. Text that is not YAML raises
    `yaml.YAMLError`, and YAML that is no list of label specs raises `pydantic.ValidationError`."""
    return _LABEL_SPECS.validate_python(yaml.safe_load(text))


def declared_label_names(text: str) -> tuple[str, ...]:
    """The names of the labels that the text of `.github/labels.yml` declares, with the errors of
    `declared_label_specs`."""
    return tuple(spec.name for spec in declared_label_specs(text))


def requested_labels(title: str) -> tuple[str | None, str | None]:
    """The `type/*` label and the `scope/*` label that `title` asks for, declared or not. A title
    with no type or no scope asks for nothing for it."""
    kind = commit_type(title)
    scope = commit_scope(title)
    return (
        CONST_ROADMAP_COMMIT_TYPE_LABELS.get(kind) if kind else None,
        f"{CONST_ROADMAP_SCOPE_LABEL_PREFIX}{scope}" if scope else None,
    )


def title_labels(title: str, declared: Collection[str]) -> TitleLabels:
    """The labels that `title` gives, from the label names `declared`. A type with no declared
    label gives none. A scope with no declared label gives none, and is named in
    `undeclared_scope`. A title with no type or no scope gives nothing for it."""
    type_label, scope_label = requested_labels(title)
    if type_label not in declared:
        type_label = None
    if scope_label and scope_label not in declared:
        return TitleLabels(type_label, None, scope_label)
    return TitleLabels(type_label, scope_label)
