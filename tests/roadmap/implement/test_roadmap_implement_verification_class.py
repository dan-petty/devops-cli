"""The class of a failed verification command comes from the program that runs it (#3577).

`verification_class` reads the argv of a verification command and gives the `FailureClass` of its
program: pytest is a test, mypy is types and ruff is lint, and the row of `devops ci` gives the same
three. A program that names none of them has no class, so the step still gives its failure a repair
turn and the message names no class. Each test imports `verification_class` in its own body, so the
module collects on a commit that lacks it and the test fails on its assertion.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement_shell_policy import read_verification


def _argv(command: str) -> list[str]:
    """The argv of the verification `command`, which the shell policy admits."""
    found = read_verification(command)
    assert not isinstance(found, str), found
    return found.argv


def test_a_pytest_command_has_the_class_test() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv("uv run pytest tests/roadmap/implement/test_roadmap_implement_shell_policy.py")

    assert verification_class(argv) is FailureClass.TEST


def test_a_mypy_command_has_the_class_types() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv("uv run mypy src/devops_cli/roadmap/failure.py")

    assert verification_class(argv) is FailureClass.TYPES


def test_a_ruff_command_has_the_class_lint() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv("uv run ruff check src/devops_cli/roadmap/failure.py")

    assert verification_class(argv) is FailureClass.LINT


def test_a_devops_ci_test_command_has_the_class_test() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv(
        "uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py"
    )

    assert verification_class(argv) is FailureClass.TEST


@pytest.mark.parametrize(
    ("row", "klass"),
    [("lint", FailureClass.LINT), ("typecheck", FailureClass.TYPES)],
)
def test_a_devops_ci_row_has_the_class_of_its_program(row: str, klass: FailureClass) -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv(f"uv run devops ci {row}")

    assert verification_class(argv) is klass


def test_a_devops_command_that_names_no_class_has_none() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv("uv run devops docs check")

    assert verification_class(argv) is None


def test_a_program_that_names_no_class_has_none() -> None:
    from devops_cli.roadmap.implement.implement_shell_policy import verification_class

    argv = _argv("uv run grep -n ruff src/")

    assert verification_class(argv) is None
