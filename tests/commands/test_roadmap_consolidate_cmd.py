"""`devops roadmap consolidate` (#3740): its help, its dry run, its plan and its decline, through
the command layer with the model, the embedder and the roadmap store faked at their edges."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from devops_cli.roadmap.consolidate import read_plan

from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_data_path
from devops_cli.lang import HELP
from devops_cli.roadmap.stores.store import ConsolidateRecordKey, ItemField
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT

REPO = "example/roadmap"
BODY = "The parser in src/a.py drops a row in `parse_row`."


def _stage(name: str) -> Callable[[str], bool]:
    return lambda prompt: json.loads(prompt).get("stage") == name


def _proposal(prompt: str) -> str:
    seen = json.loads(prompt)
    return json.dumps(
        {
            "anchor": seen["anchor"]["number"],
            "shape": "merge-into-anchor",
            "theme": "parser rows",
            "root_cause": "the parser drops a row",
            "consistency_gained": "one issue",
            "risks": [],
            "confidence": 0.7,
            "members": [
                {"number": m["number"], "action": "merge", "reason": "same fault", "citations": []}
                for m in seen["members"]
            ],
        }
    )


@pytest.fixture
def board(roadmap_store: InMemoryRoadmapStore, model_fake: ModelFake, embedder: Any) -> ModelFake:
    for _ in range(2):
        roadmap_store.seed_issue(
            "Parser drops a row", body=BODY, fields={ItemField.PRIORITY: "P2-Medium"}
        )
    model_fake.route(_stage("proposal"), _proposal)
    model_fake.route(_stage("refutation"), json.dumps({"verdict": "kept", "reasons": ["same"]}))
    return model_fake


def _plan_files() -> list[Path]:
    folder = resolve_data_path(load_settings().data.dir) / "roadmap/consolidate"
    return sorted(p for p in folder.glob("*.json") if p.name != "embeddings.json")


def test_the_help_names_every_option_and_the_page_and_the_page_exists(
    cli: Callable[..., Any],
) -> None:
    result = cli("roadmap", "consolidate", "--help")

    assert result.exit_code == 0, result.output
    for option in ("--repo", "--ref", "--limit", "--dry-run", "--confirm", "--decline"):
        assert option in result.output
    assert "docs/roadmap/consolidate.md" in HELP.roadmap.consolidate
    assert (REPO_ROOT / "docs/roadmap/consolidate.md").is_file()


def test_a_run_prints_the_summary_and_writes_the_plan_and_no_github_change(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, board: ModelFake
) -> None:
    result = cli("roadmap", "consolidate", "--repo", REPO)

    assert result.exit_code == 0, result.output
    assert "merge-into-anchor" in result.stdout
    (written,) = _plan_files()
    assert read_plan(written).repo == REPO
    assert roadmap_store.job_writes() == []
    assert len(board.calls) == 2


def test_a_dry_run_makes_no_request_no_model_call_and_no_file(
    cli: Callable[..., Any],
    roadmap_store_repos: list[str],
    board: ModelFake,
) -> None:
    result = cli("roadmap", "consolidate", "--repo", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert "model call" in result.stdout
    assert (roadmap_store_repos, board.calls, _plan_files()) == ([], [], [])


def test_an_unreachable_gateway_exits_non_zero_names_the_gateway_and_writes_no_plan(
    cli: Callable[..., Any],
    board: ModelFake,
    config: Callable[..., Path],
) -> None:
    config(**{"ai.gateway_enabled": True, "ai.gateway_url": "http://example.com:4000"})
    board.route_error(_stage("proposal"), ConnectionError("down"))

    result = cli("roadmap", "consolidate", "--repo", REPO)

    assert result.exit_code == 1
    assert "http://example.com:4000" in result.output
    assert _plan_files() == []


def test_decline_writes_the_job_record_only_with_confirm(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, board: ModelFake
) -> None:
    cli("roadmap", "consolidate", "--repo", REPO)
    (written,) = _plan_files()
    group = read_plan(written).groups[0].id

    preview = cli("roadmap", "consolidate", "--repo", REPO, "--decline", group)
    assert preview.exit_code == 0, preview.output
    assert roadmap_store.job_writes() == []

    done = cli("roadmap", "consolidate", "--repo", REPO, "--decline", group, "--confirm")
    assert done.exit_code == 0, done.output
    anchor = roadmap_store.item(1)
    assert anchor is not None
    assert anchor.job_record[ConsolidateRecordKey.DECLINED] == group


def test_confirm_without_decline_is_refused(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, board: ModelFake
) -> None:
    result = cli("roadmap", "consolidate", "--repo", REPO, "--confirm")

    assert result.exit_code == 1
    assert "--decline" in result.output
    assert board.calls == []
