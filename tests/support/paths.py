"""The repository root and its test data directories, the same for a test module at any depth
(#1312).

They are found from the `tests` package, which the import system has already located, so nothing
counts a module's parents and a module moved into a subdirectory reads the same paths. They are
constants rather than fixtures because module-level constants and `parametrize` lists need a
path at import, before a fixture such as pytest's `rootpath` can give one.

No conftest and no module that defines a fixture or hook imports this one, so a change here runs
only the test modules that import it rather than the whole suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import tests

TESTS_ROOT: Final[Path] = Path(tests.__file__).resolve().parent
REPO_ROOT: Final[Path] = TESTS_ROOT.parent
FIXTURES: Final[Path] = TESTS_ROOT / "fixtures"
GOLDEN: Final[Path] = TESTS_ROOT / "golden"
