"""Tests for roadmap pull labels: adding, removing, and finding stale labels."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.git import GitHubOperationError, GitHubUnauthenticatedError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.pull_labels import add_pull_labels, remove_pull_labels, stale_labels
from devops_cli.roadmap.title_labels import TitleLabels


def test_add_pull_labels_adds_each_label() -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", pull_request=True)
    add_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert store._roadmap.issues[pull].labels == ("type/bug", "scope/ai")


def test_add_pull_labels_tries_remaining_when_one_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", pull_request=True)
    real_label = store.label_issue

    def faulty_label(number: int, label: str) -> None:
        if label == "type/bug":
            raise GitHubOperationError("refused", operation="label_issue")
        real_label(number, label)

    monkeypatch.setattr(store, "label_issue", faulty_label)
    with pytest.raises(GitHubOperationError, match="type/bug could not be added"):
        add_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert store._roadmap.issues[pull].labels == ("scope/ai",)


def test_add_pull_labels_passes_unauthenticated_and_stops_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", pull_request=True)
    tried: list[str] = []

    def unauth_label(number: int, label: str) -> None:
        tried.append(label)
        if label == "type/bug":
            raise GitHubUnauthenticatedError("bad token", operation="label_issue")
        store._roadmap.issues[number].labels += (label,)

    monkeypatch.setattr(store, "label_issue", unauth_label)
    with pytest.raises(GitHubUnauthenticatedError, match="bad token"):
        add_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert tried == ["type/bug"]
    assert store._roadmap.issues[pull].labels == ()


def test_remove_pull_labels_removes_each_label() -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", labels=("type/bug", "scope/ai"), pull_request=True)
    remove_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert store._roadmap.issues[pull].labels == ()


def test_remove_pull_labels_tries_remaining_when_one_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", labels=("type/bug", "scope/ai"), pull_request=True)
    real_unlabel = store.unlabel_issue

    def faulty_unlabel(number: int, label: str) -> None:
        if label == "type/bug":
            raise GitHubOperationError("refused", operation="unlabel_issue")
        real_unlabel(number, label)

    monkeypatch.setattr(store, "unlabel_issue", faulty_unlabel)
    with pytest.raises(GitHubOperationError, match="type/bug could not be removed"):
        remove_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert store._roadmap.issues[pull].labels == ("type/bug",)


def test_remove_pull_labels_passes_unauthenticated_and_stops_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    pull = store.seed_issue("pull", labels=("type/bug", "scope/ai"), pull_request=True)
    tried: list[str] = []

    def unauth_unlabel(number: int, label: str) -> None:
        tried.append(label)
        if label == "type/bug":
            raise GitHubUnauthenticatedError("bad token", operation="unlabel_issue")

    monkeypatch.setattr(store, "unlabel_issue", unauth_unlabel)
    with pytest.raises(GitHubUnauthenticatedError, match="bad token"):
        remove_pull_labels(store, pull, ("type/bug", "scope/ai"))
    assert tried == ["type/bug"]
    assert store._roadmap.issues[pull].labels == ("type/bug", "scope/ai")


def test_stale_labels_returns_held_old_excluding_new_in_held_order() -> None:
    held = ("type/docs", "scope/ai", "scope/openspec", "custom/person")
    old = TitleLabels(type_label="type/docs", scope_label="scope/openspec")
    new = TitleLabels(type_label="type/bug", scope_label="scope/ai")
    assert stale_labels(held, old, new) == ("type/docs", "scope/openspec")


def test_stale_labels_excludes_labels_not_given_by_old_title() -> None:
    held = ("type/docs", "scope/openspec", "custom/label")
    old = TitleLabels(type_label="type/docs")
    new = TitleLabels(type_label="type/bug")
    assert stale_labels(held, old, new) == ("type/docs",)


def test_stale_labels_excludes_labels_not_held() -> None:
    held = ("type/docs",)
    old = TitleLabels(type_label="type/docs", scope_label="scope/openspec")
    new = TitleLabels(type_label="type/bug")
    assert stale_labels(held, old, new) == ("type/docs",)
