"""The entries of a stage filter: `family=value` over the label families of the roadmap (#2659).

`roadmap.stage.filter` and `--filter` take the same entries, so the settings refuse a bad entry
when they load, with the check the command uses. The module imports no model client and no GitHub
code, so the settings can import it.
"""

from __future__ import annotations

from typing import Final

from devops_cli.exceptions import ValidationError
from devops_cli.lang import MESSAGES

FILTER_FAMILIES: Final[tuple[str, ...]] = ("status", "priority", "type", "value", "effort")


def split_filter_entry(option: str) -> tuple[str, str]:
    """The family and the value of `option`, each trimmed and in lower case.

    An option that is not `family=value`, and a family outside `FILTER_FAMILIES`, raise
    `ValidationError` that names the option or the family.
    """
    texts = MESSAGES.roadmap
    family, _, value = option.partition("=")
    family, value = family.strip().lower(), value.strip().lower()
    if not family or not value:
        raise ValidationError(texts.stage_filter_form.format(option=option), field="filter")
    if family not in FILTER_FAMILIES:
        raise ValidationError(
            texts.stage_filter_family.format(
                option=option, family=family, families=", ".join(FILTER_FAMILIES)
            ),
            field="filter",
        )
    return family, value


__all__ = ["FILTER_FAMILIES", "split_filter_entry"]
