"""The kinds of the lines of the inbox, in the order the inbox lists them (#3494).

The command module builds the `--kind` option from this enum. It lives apart from `inbox.py`,
which imports the refine module and so the agent framework, and `devops roadmap --help` must not
load that framework (`tests/gate/startup_imports.py`).
"""

from enum import StrEnum


class InboxKind(StrEnum):
    """What a line of the inbox is. The members are in the order the inbox lists them."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    RELEASE = "release"
    BLOCKED = "blocked"
    REFINE = "refine"
    SPLIT = "split"
    ALTERNATIVES = "alternatives"
    FAILED = "failed"
    DRAFT = "draft"
    CLAIM = "claim"
    LABELS = "labels"
    QUEUE = "queue"
    PERSON = "person"
    OWNER = "owner"
