"""The shared spend ledger fixture (#1310)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from devops_cli.ai.spend.ledger import SpendLedger


@pytest.fixture
def spend_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SpendLedger:
    """A fresh ledger that every recorded call in the test writes to."""
    from devops_cli.ai.spend import ledger as ledger_module

    ledger = ledger_module.SpendLedger(db_path=tmp_path / "spend.db")
    monkeypatch.setattr(ledger_module, "_GLOBAL_LEDGER", ledger)
    return ledger
