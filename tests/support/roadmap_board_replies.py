"""What GitHub answers a roadmap store's board reads with, for a board of this repository's
issues (#1312): the board's items, the REST issues behind them, and the board's fields.

The board-read tests and the dry-run tests build the same boards from these.
"""

from __future__ import annotations

from typing import Any

REPO = "dan-petty/devops-cli"


def board_of(open_items: int, closed_items: int, *, archived: int = 0) -> dict[str, Any]:
    """A board of this repository's issues #1..: the open ones first, then the closed ones,
    then `archived` closed ones that are archived."""
    items = []
    for number in range(1, open_items + closed_items + archived + 1):
        is_open = number <= open_items
        items.append(
            {
                "id": f"PVTI_{number}",
                "content": {
                    "type": "Issue",
                    "number": number,
                    "repository": REPO,
                    "title": f"#{number}",
                    "url": f"https://github.com/{REPO}/issues/{number}",
                    "state": "OPEN" if is_open else "CLOSED",
                },
                "status": "Ready" if is_open else "Done",
                **({"isArchived": True} if number > open_items + closed_items else {}),
            }
        )
    return {"items": items, "totalCount": len(items)}


def issues_of(board: dict[str, Any]) -> list[dict[str, Any]]:
    """The REST issues of every item on `board`."""
    return [
        {
            "number": entry["content"]["number"],
            "title": entry["content"]["title"],
            "html_url": entry["content"]["url"],
            "state": entry["content"]["state"].lower(),
            "labels": [],
            "milestone": None,
        }
        for entry in board["items"]
    ]


def fields_reply() -> dict[str, Any]:
    """The board's fields as GraphQL lists them: a Status with four options, and the job record."""
    status = {
        "id": "PVTSSF_status",
        "name": "Status",
        "dataType": "SINGLE_SELECT",
        "options": [
            {"id": f"o{i}", "name": name}
            for i, name in enumerate(("New", "Ready", "Blocked", "Done"))
        ],
    }
    record = {"id": "PVTF_jobrecord", "name": "Job record", "dataType": "TEXT"}
    connection = {"totalCount": 2, "nodes": [status, record]}
    return {"data": {"repositoryOwner": {"projectV2": {"id": "PVT_board", "fields": connection}}}}
