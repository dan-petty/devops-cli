"""`devops roadmap refine` through its command line and through the due table (#1335)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.run import (
    DEFAULT_DUE_TABLE,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    PLACED,
    REPO,
    MockLLMClient,
    require_item,
    run_refine_adapter,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_cli_refine_dry_run_and_confirm(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    cli: Callable[..., Any],
) -> None:
    num = store.seed_issue("Feature to refine", body="Need refinement", fields=PLACED)
    item = require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")

    mock_llm = MockLLMClient()
    model_fake.answer(mock_llm.proposal)
    # Dry run
    res_dry = cli(
        ["roadmap", "refine", "--repo", REPO, "--source", str(git_repo), "--item", str(num)]
        + ["--dry-run"]
    )
    assert (res_dry.exit_code, store.read_issue_body(num)) == (0, "Need refinement")

    # Confirm
    res_confirm = cli(
        ["roadmap", "refine", "--repo", REPO, "--source", str(git_repo), "--item", str(num)]
        + ["--confirm"]
    )
    updated = require_item(store, num)
    assert (
        res_confirm.exit_code,
        CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(num),
        updated.status,
    ) == (0, True, CONST_ROADMAP_STATUS_READY)


def test_run_due_table_refine_adapter(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    # Verify refine row exists in DEFAULT_DUE_TABLE
    row = next((r for r in DEFAULT_DUE_TABLE if r.name == "refine"), None)
    assert row is not None
    assert row.needs_clone is True

    # Run adapter
    outcome = run_refine_adapter(store, repo=REPO, clone_path=git_repo)
    assert outcome is not None
