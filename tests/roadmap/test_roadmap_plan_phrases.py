"""The phrase check of the plan folder (#4039)."""

from __future__ import annotations

from devops_cli.roadmap.plan_phrases import declared_phrases, phrase_problems

ROOT = "openspec/changes/1-a-plan"
PHRASE = "gives a count from a tool of the plan run or from a probe line"
VARIANT = "from references or from a probe line"
PAIR = f'`("openspec/config.yaml", "{PHRASE}")`'


def _files(**texts: str) -> dict[str, str]:
    return {f"{ROOT}/{name.replace('_', '/')}.md": text for name, text in texts.items()}


def test_a_declared_pair_names_its_phrase() -> None:
    assert declared_phrases(f"Keep the pair {PAIR}.") == [PHRASE]


def test_a_declared_pair_with_no_variant_gives_no_problem() -> None:
    files = _files(
        tasks=f"Keep the pair {PAIR}.",
        proposal=f"The page {PHRASE}.",
    )

    assert phrase_problems(files) == []


def test_a_variant_in_the_proposal_is_a_problem_naming_both_spans() -> None:
    files = _files(
        tasks=f"Keep the pair {PAIR}.",
        proposal=f"The page `{VARIANT}`.",
    )

    (problem,) = phrase_problems(files)
    assert (problem.path, PHRASE in problem.message, VARIANT in problem.message) == (
        f"{ROOT}/proposal.md",
        True,
        True,
    )


def test_a_variant_in_a_spec_delta_is_a_problem() -> None:
    files = {
        f"{ROOT}/tasks.md": f"Keep the pair {PAIR}.",
        f"{ROOT}/specs/roadmap-stage/context/spec.md": f"- **WHEN** the page `{VARIANT}`\n",
    }

    (problem,) = phrase_problems(files)

    assert problem.path.endswith("specs/roadmap-stage/context/spec.md")


def test_an_unrelated_span_and_a_plan_with_no_pair_give_no_problem() -> None:
    assert phrase_problems(_files(tasks="Run `devops roadmap plan-check`.")) == []
    assert (
        phrase_problems(
            _files(
                tasks=f"Keep the pair {PAIR}.",
                proposal="Run `devops roadmap plan-check`.",
            )
        )
        == []
    )
