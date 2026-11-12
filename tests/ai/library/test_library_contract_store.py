"""`PackageIntrospector.save_to_dir`: a saved contract reads back with its modules (#1329)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.library.introspector import PackageIntrospector
from devops_cli.models.library import LibraryContract
from tests.support.library_contracts import write_demo_contract


def test_a_saved_contract_loads_back_with_its_modules_and_symbols(tmp_path: Path) -> None:
    contract = write_demo_contract(tmp_path / "source")
    store = tmp_path / "store"
    introspector = PackageIntrospector()

    saved = introspector.save_to_dir(contract, store)
    loaded = LibraryContract.model_validate_json(saved.read_text(encoding="utf-8"))

    assert (
        saved.name,
        loaded.package_name,
        loaded.version,
        sorted(loaded.modules["demolib"].functions),
        sorted(loaded.modules["demolib"].classes),
    ) == ("demolib.json", "demolib", "1.0.0", ["compute", "legacy_calc"], ["Client"])
