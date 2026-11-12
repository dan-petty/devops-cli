"""Every capability under `openspec/specs/` stays small, so that two pull requests seldom archive
into one file (#4622).

`openspec archive` 1.14.3 appends each ADDED requirement at the end of the file of its capability,
so two pull requests that archive into one capability conflict on the same lines. A capability over
the limit of `openspec/config.yaml` is split into nested capabilities `<area>/<name>`, which
`openspec list --specs` finds as `specs/<area>/<name>/spec.md`.

An area folder holds no `spec.md` of its own. A delta that still names the area, for example of a
plan made before the split, archives into a new `specs/<area>/spec.md`. This test fails until that
delta names the nested capability of its requirements.
"""

from __future__ import annotations

import re
from typing import Final

from devops_cli.config.constants import CONST_OPENSPEC_SPECS_DIR
from tests.support.paths import REPO_ROOT

# The most requirements that one capability holds: the rule of `openspec/config.yaml`.
_LIMIT: Final[int] = 80
_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement:", re.M)
_SPECS = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR


def _capabilities() -> dict[str, int]:
    """The number of requirements of each capability, by its name, flat or nested."""
    return {
        path.parent.relative_to(_SPECS).as_posix(): len(
            _REQUIREMENT.findall(path.read_text(encoding="utf-8"))
        )
        for path in sorted(_SPECS.rglob("spec.md"))
    }


def test_no_capability_holds_more_requirements_than_the_limit() -> None:
    over = {name: count for name, count in _capabilities().items() if count > _LIMIT}

    assert over == {}, f"split each capability into nested ones of at most {_LIMIT}: {over}"


def test_an_area_of_nested_capabilities_holds_no_spec_of_its_own() -> None:
    names = set(_capabilities())

    areas = sorted(name for name in names if any(other.startswith(f"{name}/") for other in names))

    assert areas == [], f"move the requirements of each area into its nested capabilities: {areas}"
