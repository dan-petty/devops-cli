"""The merge of a live GitHub ruleset into the baseline ruleset of row 10 (#7326).

The merge keeps each live rule, each live check entry and each live value that is stricter than
the baseline value, and it names each one, so row 10 never lowers a threshold that only the owner
may lower (rule 5 of `AGENTS.md`). Each test imports the merge in its body, so a test on a commit
without the module fails on an assertion instead of stopping the collection of the file.
"""

from __future__ import annotations

from typing import Any

import pytest

_CHECKS = "required_status_checks"


def _rule(kind: str, **parameters: Any) -> dict[str, Any]:
    """A rule of a ruleset, with its parameters."""
    return {"type": kind, "parameters": parameters}


def _ruleset(*rules: dict[str, Any]) -> dict[str, Any]:
    """A ruleset `main`, as the baseline file and the reply of GitHub hold it."""
    return {
        "name": "main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": list(rules),
    }


def _rule_of(ruleset: dict[str, Any], kind: str) -> dict[str, Any]:
    """The rule of a type that a merged ruleset holds."""
    return next(rule for rule in ruleset["rules"] if rule["type"] == kind)


def _parameters(ruleset: dict[str, Any], kind: str) -> dict[str, Any]:
    """The parameters of the rule of a type that a merged ruleset holds."""
    return _rule_of(ruleset, kind)["parameters"]


def _contexts(ruleset: dict[str, Any]) -> list[str]:
    """The names of the checks that the required checks rule of a merged ruleset requires."""
    return [entry["context"] for entry in _parameters(ruleset, _CHECKS)["required_status_checks"]]


def test_merge_keeps_a_live_rule_that_the_baseline_lacks() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    # A `code_coverage` rule has no definition in the baseline file, so the merge must add it.
    baseline = _ruleset(_rule("deletion"))
    live = _ruleset(_rule("deletion"), _rule("code_coverage", minimum_coverage=90))

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _rule_of(merged, "code_coverage") == _rule("code_coverage", minimum_coverage=90)
    assert warnings == ("keeps code_coverage.minimum_coverage 90",)
    assert baseline == _ruleset(_rule("deletion")), "the merge changes no baseline body"


@pytest.mark.parametrize(
    ("kind", "baseline", "live", "expected"),
    [
        (
            "code_coverage",
            {"minimum_coverage": 80},
            {"minimum_coverage": 90},
            {"minimum_coverage": 90},
        ),
        (
            "code_quality",
            {"severity": "errors"},
            {"severity": "warnings"},
            {"severity": "warnings"},
        ),
        (
            "code_scanning",
            {
                "code_scanning_tools": [
                    {"tool": "CodeQL", "security_alerts_threshold": "high_or_higher"}
                ]
            },
            {
                "code_scanning_tools": [
                    {"tool": "CodeQL", "security_alerts_threshold": "medium_or_higher"}
                ]
            },
            {
                "code_scanning_tools": [
                    {"tool": "CodeQL", "security_alerts_threshold": "medium_or_higher"}
                ]
            },
        ),
        (
            "pull_request",
            {"required_review_thread_resolution": False},
            {"required_review_thread_resolution": True},
            {"required_review_thread_resolution": True},
        ),
        (
            _CHECKS,
            {"do_not_enforce_on_create": True},
            {"do_not_enforce_on_create": False},
            {"do_not_enforce_on_create": False},
        ),
    ],
    ids=[
        "higher coverage minimum",
        "warnings kept over errors",
        "medium CodeQL threshold",
        "review thread resolution",
        "checks enforced on create",
    ],
)
def test_merge_keeps_a_stricter_live_threshold(
    kind: str, baseline: dict[str, Any], live: dict[str, Any], expected: dict[str, Any]
) -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    merged, warnings = merge_live_ruleset(
        _ruleset(_rule(kind, **baseline)), _ruleset(_rule(kind, **live)), _CHECKS
    )

    assert _parameters(merged, kind) == expected
    assert len(warnings) == len(expected)


@pytest.mark.parametrize(
    ("baseline", "live", "expected"),
    [
        (
            [],
            _rule(
                _CHECKS,
                required_status_checks=[{"context": "Lint"}],
                strict_required_status_checks_policy=True,
            ),
            {
                "required_status_checks": [{"context": "Lint"}],
                "strict_required_status_checks_policy": True,
            },
        ),
        (
            [_rule(_CHECKS, required_status_checks=[{"context": "Typecheck"}])],
            _rule(_CHECKS, required_status_checks=[{"context": "Lint"}]),
            {"required_status_checks": [{"context": "Lint"}, {"context": "Typecheck"}]},
        ),
    ],
    ids=["live required checks rule kept", "live check entry kept"],
)
def test_merge_keeps_a_live_required_checks_rule(
    baseline: list[dict[str, Any]], live: dict[str, Any], expected: dict[str, Any]
) -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    merged, warnings = merge_live_ruleset(_ruleset(*baseline), _ruleset(live), _CHECKS)

    assert _parameters(merged, _CHECKS) == expected
    assert not any(line.startswith(f"keeps {_CHECKS}.{_CHECKS} ") for line in warnings), (
        "the change line of row 10 names each required check"
    )


def test_merge_takes_the_baseline_value_of_a_weaker_live_parameter() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    baseline = _ruleset(_rule(_CHECKS, strict_required_status_checks_policy=True))
    live = _ruleset(_rule(_CHECKS, strict_required_status_checks_policy=False))

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _parameters(merged, _CHECKS) == {"strict_required_status_checks_policy": True}
    assert warnings == ()


def test_merge_keeps_an_unranked_parameter() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    # A parameter that the table does not rank stays, also when both rulesets hold it.
    live = _ruleset(_rule("pull_request", required_review_thread_resolution=True, new_setting="on"))
    baseline = _ruleset(_rule("pull_request", required_review_thread_resolution=True))

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _parameters(merged, "pull_request") == {
        "required_review_thread_resolution": True,
        "new_setting": "on",
    }
    assert warnings == ("keeps pull_request.new_setting on",)

    both = _ruleset(
        _rule("pull_request", required_review_thread_resolution=True, new_setting="off")
    )

    merged_both, warnings_both = merge_live_ruleset(both, live, _CHECKS)

    assert _parameters(merged_both, "pull_request")["new_setting"] == "on"
    assert warnings_both == ("keeps pull_request.new_setting on",)


def test_merge_names_each_kept_setting() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    # A rule without a `parameters` key keeps no such key, so the merge adds no empty one.
    baseline = _ruleset({"type": "deletion"}, _rule("code_coverage", minimum_coverage=80))
    live = _ruleset(
        {"type": "deletion"},
        _rule("code_coverage", minimum_coverage=90),
        {"type": "required_signatures"},
    )

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert warnings == (
        "keeps code_coverage.minimum_coverage 90",
        "keeps the rule required_signatures",
    )
    assert _rule_of(merged, "required_signatures") == {"type": "required_signatures"}
    assert _rule_of(merged, "deletion") == {"type": "deletion"}


def test_merge_keeps_a_scanning_tool_that_the_baseline_lacks() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    # A tool of the baseline stays, a tool that only the live rule holds stays, and a weaker live
    # threshold of a tool takes the baseline threshold.
    baseline = _ruleset(
        _rule(
            "code_scanning",
            code_scanning_tools=[
                {"tool": "CodeQL", "security_alerts_threshold": "low_or_higher"},
                {"tool": "Bandit"},
            ],
        )
    )
    live = _ruleset(
        _rule(
            "code_scanning",
            code_scanning_tools=[
                {"tool": "CodeQL", "security_alerts_threshold": "high_or_higher"},
                {"tool": "Trivy", "security_alerts_threshold": "critical"},
            ],
        )
    )

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _parameters(merged, "code_scanning")["code_scanning_tools"] == [
        {"tool": "Bandit"},
        {"tool": "CodeQL", "security_alerts_threshold": "low_or_higher"},
        {"tool": "Trivy", "security_alerts_threshold": "critical"},
    ]
    assert warnings == (
        "keeps code_scanning.code_scanning_tools.Trivy.security_alerts_threshold critical",
    )


def test_merge_names_a_kept_list_parameter() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    baseline = _ruleset(_rule("required_deployments", required_deployment_environments=["release"]))
    live = _ruleset(
        _rule("required_deployments", required_deployment_environments=["release", "staging"])
    )

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _parameters(merged, "required_deployments") == {
        "required_deployment_environments": ["release", "staging"]
    }
    assert warnings == (
        "keeps required_deployments.required_deployment_environments release, staging",
    )


def test_merge_adds_a_baseline_rule_and_check() -> None:
    from devops_cli.github.onboard.ruleset_merge import merge_live_ruleset

    baseline = _ruleset(
        _rule("deletion"),
        _rule(_CHECKS, required_status_checks=[{"context": "Lint"}]),
    )
    live = _ruleset(_rule(_CHECKS, required_status_checks=[{"context": "Typecheck"}]))

    merged, warnings = merge_live_ruleset(baseline, live, _CHECKS)

    assert _contexts(merged) == ["Lint", "Typecheck"]
    assert _rule_of(merged, "deletion") == _rule("deletion")
    assert warnings == ()
