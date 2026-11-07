"""`PackageIntrospector.introspect_package`: the contract of an installed package (#1329)."""

from __future__ import annotations

import pytest

from devops_cli.ai.library.introspector import PackageIntrospector
from devops_cli.exceptions.ai import LibraryNotFoundError


def test_a_package_that_is_not_installed_is_refused_by_name() -> None:
    with pytest.raises(LibraryNotFoundError, match="nonexistent_pkg_xyz_123"):
        PackageIntrospector().introspect_package("nonexistent_pkg_xyz_123")


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_an_installed_package_gives_its_modules_and_symbols() -> None:
    contract = PackageIntrospector().introspect_package("pydantic", max_depth=1)

    assert (
        contract.package_name,
        contract.total_modules >= 1,
        "BaseModel" in contract.symbols_index or contract.total_classes > 0,
    ) == ("pydantic", True, True)
