"""`devops roadmap implement` (#3097): the message of a step holds the `AGENTS.md` of the checkout
and the sections of the documents that it routes the group to.

The checkout has a small `AGENTS.md` and a small `docs/TESTING.md`. A stub model with a script
captures the first request, as `test_roadmap_implement_step.py` does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.roadmap.implement_step import FixRequest, build_step_inputs, run_step
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.step_files import parse_task_groups
from devops_cli.roadmap.step_rules import RULES_HEADING, route_heading, rules_sections
from tests.support.fakes.process import ProcessFake
from tests.support.implement_step import WINDOW, git, make_checkout
from tests.support.model_script import ModelScript, say

pytestmark = pytest.mark.usefixtures("keyring_store")

AGENTS = "# Agents\n\nRule 12: scratch files go under `.data/agent/scratch/`.\n"
TESTING = "# Testing\n\n## Conventions\n\n### Doubles\n\nDouble only the edges.\n"
TESTING_HEADING = route_heading("docs/TESTING.md")
MANIFEST_TASKS = "# Tasks\n\n## 1. A manifest\n\n- [ ] Change `k8s/sample.yaml`\n"


def _with_rules(checkout: Path) -> Path:
    """The checkout with `AGENTS.md` and `docs/TESTING.md`, committed."""
    (checkout / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
    (checkout / "docs" / "TESTING.md").write_text(TESTING, encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "rules")
    return checkout


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return _with_rules(implement_checkout)


def test_the_message_holds_agents_md_verbatim_under_its_heading(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert f"# {RULES_HEADING}\n\n{AGENTS.strip()}" in inputs.message


def test_the_rules_come_before_the_item(store: InMemoryRoadmapStore, checkout: Path) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert inputs.message.index(RULES_HEADING) < inputs.message.index("# Item #1")


def test_the_first_request_of_the_model_holds_agents_md(
    store: InMemoryRoadmapStore, checkout: Path, implement_programs: ProcessFake
) -> None:
    script = ModelScript(say("Done."))

    run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)

    contents = [str(getattr(part, "content", "")) for part in script.seen[0][0].parts]
    assert any(AGENTS.strip() in content for content in contents)


def test_a_group_that_changes_a_test_gets_the_testing_sections(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    assert f"{TESTING_HEADING}\n\n### Doubles\n\nDouble only the edges." in inputs.message


def test_a_group_that_changes_only_a_document_gets_no_testing_sections(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=2, source=checkout, window=WINDOW)

    assert (RULES_HEADING in inputs.message, TESTING_HEADING in inputs.message) == (True, False)


def test_a_group_that_changes_only_a_manifest_gets_no_testing_sections(
    store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    manifest = _with_rules(make_checkout(tmp_path / "manifest", MANIFEST_TASKS))

    inputs = build_step_inputs(store, item=1, group=1, source=manifest, window=WINDOW)

    assert (RULES_HEADING in inputs.message, TESTING_HEADING in inputs.message) == (True, False)


def test_a_fix_step_holds_agents_md_and_no_routed_section(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    fix = FixRequest(check="lint", log="E501 line too long in tests/test_sample.py")

    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW, fix=fix)

    assert (RULES_HEADING in inputs.message, TESTING_HEADING in inputs.message) == (True, False)


def test_every_section_of_the_rules_is_in_the_message_exactly(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)
    [group] = [g for g in parse_task_groups(inputs.tasks_md) if g.number == 1]

    sections = rules_sections(checkout, group)

    assert len(sections) > 1
    assert [section for section in sections if section not in inputs.message] == []


def test_the_tokens_of_the_step_count_the_rules(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    inputs = build_step_inputs(store, item=1, group=1, source=checkout, window=WINDOW)

    rules = f"# {RULES_HEADING}\n\n{AGENTS.strip()}"
    assert inputs.tokens >= count_tokens(inputs.instructions) + count_tokens(rules)


def test_rules_that_do_not_fit_the_window_refuse_the_step(
    store: InMemoryRoadmapStore, checkout: Path
) -> None:
    window = CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS + 3000
    build_step_inputs(store, item=1, group=1, source=checkout, window=window)
    (checkout / "AGENTS.md").write_text("Rule. " * 4000, encoding="utf-8")
    git(checkout, "commit", "-q", "-am", "long rules")

    with pytest.raises(RoadmapImplementError, match="The limit is 3000 tokens"):
        build_step_inputs(store, item=1, group=1, source=checkout, window=window)
