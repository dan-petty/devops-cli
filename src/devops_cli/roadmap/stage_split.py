"""`devops roadmap stage`: split model call shared by stage and implement jobs (#3057)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final, cast

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.stage_change import StageSplit

SPLIT_TASK: Final[str] = "roadmap_stage_split.md"


def ask_split(client: Any, request: Mapping[str, Any]) -> StageSplit:
    """Ask the model to split the groups over budget."""
    return cast(
        StageSplit,
        client.chat_structured(
            load_task_prompt(SPLIT_TASK),
            json.dumps(request, ensure_ascii=False, indent=1),
            StageSplit,
            max_retries=1,
        ),
    )
