"""Tests for title_labels utilities including declared_type_labels (#1359)."""

from __future__ import annotations

from devops_cli.roadmap.title_labels import declared_type_labels


def test_declared_type_labels_filters_type_labels_excluding_epic() -> None:
    declared = (
        "type/bug",
        "type/feature",
        "type/epic",
        "scope/ai",
        "type/infra",
        "status/ready",
    )
    assert declared_type_labels(declared) == ("type/bug", "type/feature", "type/infra")


def test_declared_type_labels_returns_empty_when_no_type_label_present() -> None:
    declared = ("scope/ai", "status/ready", "type/epic")
    assert declared_type_labels(declared) == ()
