"""`PackageIntrospector.save_to_dir` and `load_from_dir`: a contract survives a round trip (#1329)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.library.introspector import PackageIntrospector
from tests.support.library_contracts import write_demo_contract


def test_a_saved_contract_loads_back_with_its_modules_and_symbols(tmp_path: Path) -> None:
    contract = write_demo_contract(tmp_path / "source")
    store = tmp_path / "store"
    introspector = PackageIntrospector()

    saved = introspector.save_to_dir(contract, store)
    loaded = introspector.load_from_dir("demolib", store)

    assert loaded is not None
    assert (
        saved.name,
        loaded.package_name,
        loaded.version,
        sorted(loaded.modules["demolib"].functions),
        sorted(loaded.modules["demolib"].classes),
    ) == ("demolib.json", "demolib", "1.0.0", ["compute", "legacy_calc"], ["Client"])


def test_a_package_that_was_never_saved_loads_as_none(tmp_path: Path) -> None:
    assert PackageIntrospector().load_from_dir("never-saved", tmp_path) is None


def test_a_contract_file_that_is_not_valid_loads_as_none(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    assert PackageIntrospector().load_from_dir("broken", tmp_path) is None
