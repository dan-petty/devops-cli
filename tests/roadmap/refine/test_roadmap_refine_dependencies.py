"""The blocker lines of a Dependencies section, and the mentions that name no dependency (#6451).

Only a blocker line holds an item back: a list item whose first word is an issue reference, a
line that holds issue references only, or a line that starts with `Merge first`. A parent, a
child, a related issue, a reverse link and the source line of intake name no dependency.
"""

from __future__ import annotations

from devops_cli.roadmap.dependencies import open_dependency
from devops_cli.roadmap.refine.refine import body_dependencies
from devops_cli.roadmap.stores.store import GitHubState, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

PRIORITY = "P2-Medium"


def _seed(store: InMemoryRoadmapStore, title: str, *, body: str = "") -> int:
    """An open issue whose body holds `body`."""
    return store.seed_issue(
        title,
        body=body,
        fields={ItemField.PRIORITY: PRIORITY},
        state=GitHubState.OPEN,
    )


def test_body_dependencies_names_only_a_blocker_line() -> None:
    """A Dependencies section names a dependency only on a blocker line: `None.` and a
    `Source: #N` paragraph name none, a parent, a child, a related issue, a reverse link and a
    sentence that mentions an issue name none, a list item and a `Merge first` line name one, and
    a paragraph of issue references names each (#6451)."""
    assert (
        body_dependencies("## Dependencies\n\nNone.\n\nSource: #4989\n"),
        body_dependencies(
            "## Dependencies\n\nPart of #5014\n\nChild 5 of #4893\n\nRelated: #4408\n\n"
            "#4691 needs this item\n\nThis item blocks #5134 step 6\n"
        ),
        body_dependencies("## Dependencies\n\n- #4989\n\nMerge first: #5134\n"),
        body_dependencies("## Dependencies\n\n#2, #4\n"),
    ) == ([], [], [4989, 5134], [2, 4])


def test_an_open_related_issue_holds_no_item_back() -> None:
    """The Dependencies section names a related open issue and no blocker, so the item gets no
    dependency reason (#6451)."""
    store = InMemoryRoadmapStore()
    related = _seed(store, "fix(roadmap): the related item")
    waiting = _seed(
        store,
        "fix(roadmap): the waiting item",
        body=f"### Dependencies\n\nRelated: #{related}\n",
    )
    item = store.item(waiting)

    assert item is not None
    assert open_dependency(item, store, store.open_items()) is None
