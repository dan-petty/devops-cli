"""Tests for repository .claude/settings.json invariants."""

from __future__ import annotations

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXPECTED_DENY_RULES = (
    "Read(//**/.claude/settings.local.json)",
    "Read(~/.claude/settings.json)",
    "Read(~/.kube/**)",
)


def test_claude_code_settings_parses_and_enforces_deny_rules() -> None:
    """Verify .claude/settings.json is valid JSON and permissions.deny holds required rules."""
    settings_path = _PROJECT_ROOT / ".claude" / "settings.json"
    assert settings_path.is_file(), f"Missing {settings_path}"

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    permissions = data.get("permissions", {})
    deny_rules = permissions.get("deny", [])

    assert (
        isinstance(deny_rules, list),
        all(rule in deny_rules for rule in _EXPECTED_DENY_RULES),
    ) == (True, True)
