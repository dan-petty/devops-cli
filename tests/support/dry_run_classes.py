"""The check of the dry-run class of each command in the table of a dry-run test (#2230).

A table row starts with the name of the command and its callback, such as
`("tf apply", tf_apply, ["tf", "apply", "--dry-run"])`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from devops_cli.dry_run import get_dry_run_class


def misclassified(rows: Iterable[Sequence[Any]], expected: str) -> dict[str, str | None]:
    """The commands of `rows` whose dry-run class is not `expected`, each with the class it has."""
    return {row[0]: actual for row in rows if (actual := get_dry_run_class(row[1])) != expected}
