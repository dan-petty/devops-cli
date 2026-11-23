"""Tests for project digest generation from code at run time (#3904)."""

from __future__ import annotations

from pydantic_core import PydanticUndefined

from devops_cli.ai.project_digest import command_facts, settings_sections
from devops_cli.docs.generator import DocGenerator, iter_settings_fields


def test_command_facts_lists_each_registered_command_and_no_absent_one() -> None:
    generator = DocGenerator()
    groups = generator.introspect_all_groups()
    facts = command_facts(groups)

    # Asserts that command_facts holds each group and command of DocGenerator.introspect_all_groups
    command_keys = {(f["group"], f["command"]) for f in facts}
    for g in groups:
        assert g.name in {f["group"] for f in facts}
        for cmd in g.commands:
            assert (g.name, cmd.name) in command_keys
            matching = [f for f in facts if f["group"] == g.name and f["command"] == cmd.name]
            assert len(matching) >= 1
            expected_help = cmd.description or cmd.summary or ""
            assert matching[0]["help"] == expected_help

    # Asserts that a command name that no module registers is absent
    assert ("roadmap", "nonexistent_command_xyz") not in command_keys
    assert ("nonexistent_group_xyz", "some_cmd") not in command_keys

    # Asserts that settings_sections holds each section and field of Settings
    sections = settings_sections()
    assert isinstance(sections, dict)

    for sec_key, sec_model, field_name, field_info in iter_settings_fields():
        assert sec_key in sections
        field_entries = sections[sec_key]
        dotted_name = field_name if sec_model is None else f"{sec_key}.{field_name}"
        matching = [f for f in field_entries if f["name"] == dotted_name]
        assert len(matching) == 1
        entry = matching[0]

        # Asserts default or default-factory name
        if field_info.default_factory is not None:
            factory_name = getattr(
                field_info.default_factory, "__name__", str(field_info.default_factory)
            )
            assert entry["default"] == factory_name
        elif field_info.default is not PydanticUndefined:
            val = field_info.default
            expected = val if isinstance(val, (int, float, bool, str)) or val is None else str(val)
            assert entry["default"] == expected
        else:
            assert entry["default"] is None
