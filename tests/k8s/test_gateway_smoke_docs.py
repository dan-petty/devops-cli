"""The gateway smoke check documents one call for each hosted group (#4428).

The LiteLLM upgrade changes the provider path of each hosted group, and no offline test reaches a
provider. The calls live in `k8s/README.md`, and this module reads them there.
"""

from __future__ import annotations

import re

from tests.support.paths import REPO_ROOT

README = (REPO_ROOT / "k8s" / "README.md").read_text(encoding="utf-8")
HEADING = "#### Smoke check after a gateway upgrade"
_SECTION = re.search(rf"{re.escape(HEADING)}\n(.*?)(?=\n#### |\n### |\n## |\Z)", README, re.DOTALL)
SECTION = "" if _SECTION is None else _SECTION.group(1)
HOSTED_GROUPS = {
    "claude-sonnet-5-5": "ANTHROPIC_API_KEY",
    "claude-haiku-5-5": "ANTHROPIC_API_KEY",
    "gemini-3.8-flash": "GEMINI_API_KEY",
    "deepseek-v4.1-flash-1017": "OPENROUTER_API_KEY",
}
STRUCTURED_GROUP = "claude-sonnet-5-5"


def _calls() -> list[str]:
    """Each `curl` command of the section, one per line."""
    return [line for line in SECTION.splitlines() if line.startswith("curl ")]


def test_each_hosted_group_has_one_chat_completion_call() -> None:
    calls = [call for call in _calls() if '"response_format"' not in call]
    named = {group: sum(f'"model":"{group}"' in call for call in calls) for group in HOSTED_GROUPS}

    assert (named, all("/v1/chat/completions" in call for call in calls), len(calls)) == (
        dict.fromkeys(HOSTED_GROUPS, 1),
        True,
        len(HOSTED_GROUPS),
    )


def test_the_provider_key_of_each_group_is_named() -> None:
    assert {
        group: SECTION.count(f"| `{group}` | `{key}` |") for group, key in HOSTED_GROUPS.items()
    } == dict.fromkeys(HOSTED_GROUPS, 1)


def test_only_the_gateway_key_is_in_each_call() -> None:
    authorities = [call for call in SECTION.splitlines() if "Authorization:" in call]
    provider_headers = [
        name for name in (*HOSTED_GROUPS.values(), "X-Api-Key") if f"{name}:" in SECTION
    ]

    assert (
        len(authorities),
        all('Authorization: Bearer $KEY"' in call for call in authorities),
        provider_headers,
    ) == (5, True, [])


def test_the_structured_call_asks_for_a_json_schema() -> None:
    structured = [call for call in _calls() if '"response_format"' in call]

    assert (
        len(structured),
        all(f'"model":"{STRUCTURED_GROUP}"' in call for call in structured),
        all('"type":"json_schema"' in call and '"schema":' in call for call in structured),
    ) == (1, True, True)


def test_the_steps_name_the_record_and_the_fix_issue() -> None:
    assert (
        "onto the new image" in SECTION,
        "comment on the upgrade issue" in SECTION,
        "devops gh issue create --label source/agent" in SECTION,
        "priority/" in SECTION,
    ) == (True, True, True, False)
