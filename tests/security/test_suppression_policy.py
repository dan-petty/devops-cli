"""Suppression policy files: matching, expiry and inheritance."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from devops_cli.security.suppression import (
    SuppressionPolicyError,
    SuppressionRule,
    empty_policy,
    load_policy,
)
from tests.support.builders import make_normalized_finding


def write_policy(path: Path, body: str) -> Path:
    """Write a suppression policy file."""
    path.write_text(body)
    return path


def test_a_rule_glob_suppresses_matching_findings(tmp_path: Path) -> None:
    """Suppressing by rule is the common case."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B6*\n    reason: accepted\n",
        )
    )
    kept, suppressed = policy.apply(
        [make_normalized_finding(rule_id="B602"), make_normalized_finding(rule_id="B307")]
    )
    assert ([f.rule_id for f in kept], len(suppressed)) == (["B307"], 1)


def test_a_path_glob_scopes_a_suppression(tmp_path: Path) -> None:
    """A suppression accepted for test fixtures must not apply to production code."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            'suppressions:\n  - rule: "*"\n    paths: ["tests/**"]\n',
        )
    )
    kept, _ = policy.apply(
        [
            make_normalized_finding(path="tests/fixtures/a.py"),
            make_normalized_finding(path="src/app.py"),
        ]
    )
    assert [finding.path for finding in kept] == ["src/app.py"]


def test_a_tool_glob_scopes_a_suppression(tmp_path: Path) -> None:
    """Accepting one tool's opinion must not silence another's."""
    policy = load_policy(write_policy(tmp_path / "p.yml", 'suppressions:\n  - tools: ["bandit"]\n'))
    kept, _ = policy.apply(
        [make_normalized_finding(tool="bandit"), make_normalized_finding(tool="semgrep")]
    )
    assert [finding.tool for finding in kept] == ["semgrep"]


def test_a_fingerprint_suppression_matches_exactly_one_finding(tmp_path: Path) -> None:
    """A fingerprint accepts one specific result, not a class of them."""
    target = make_normalized_finding()
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            f"suppressions:\n  - fingerprint: {target.fingerprint}\n",
        )
    )
    kept, suppressed = policy.apply([target, make_normalized_finding(path="other.py")])
    assert ([f.path for f in kept], len(suppressed)) == (["other.py"], 1)


def test_an_expired_suppression_stops_suppressing(tmp_path: Path) -> None:
    """A suppression that never lapses is indistinguishable from a blind spot."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2020-01-01\n",
        )
    )
    kept, suppressed = policy.apply([make_normalized_finding()], today=date(2026, 9, 21))
    assert (len(kept), len(suppressed)) == (1, 0)


def test_a_suppression_expiring_today_is_still_in_force(tmp_path: Path) -> None:
    """Expiry is end-of-day, so a policy does not lapse a day early."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2026-09-21\n",
        )
    )
    kept, _ = policy.apply([make_normalized_finding()], today=date(2026, 9, 21))
    assert kept == []


def test_an_unparseable_expiry_is_treated_as_expired(tmp_path: Path) -> None:
    """Defaulting a typo to 'never' turns a mistake into a permanent suppression."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: not-a-date\n",
        )
    )
    kept, _ = policy.apply([make_normalized_finding()])
    assert len(kept) == 1


def test_expired_rules_are_reported_for_review(tmp_path: Path) -> None:
    """A lapsed suppression should prompt a decision, not vanish silently."""
    policy = load_policy(
        write_policy(
            tmp_path / "p.yml",
            "suppressions:\n  - rule: B602\n    expires: 2020-01-01\n",
        )
    )
    assert [rule.rule for rule in policy.expired_rules(date(2026, 9, 21))] == ["B602"]


def test_a_policy_inherits_rules_from_the_baseline_it_extends(tmp_path: Path) -> None:
    """A shared baseline must not be copied into every repository that needs it."""
    write_policy(tmp_path / "base.yml", "suppressions:\n  - rule: SHARED\n")
    policy = load_policy(
        write_policy(
            tmp_path / "child.yml",
            "extends: base.yml\nsuppressions:\n  - rule: LOCAL\n",
        )
    )
    assert [rule.rule for rule in policy.rules] == ["LOCAL", "SHARED"]


def test_local_rules_are_matched_before_inherited_ones(tmp_path: Path) -> None:
    """A repository must be able to override a baseline, not only add to it."""
    write_policy(tmp_path / "base.yml", 'suppressions:\n  - rule: "*"\n    reason: baseline\n')
    policy = load_policy(
        write_policy(
            tmp_path / "child.yml",
            'extends: base.yml\nsuppressions:\n  - rule: "B602"\n    reason: local\n',
        )
    )
    rule = policy.suppresses(make_normalized_finding())
    assert rule is not None
    assert rule.reason == "local"


def test_a_policy_extending_several_baselines_collects_all_of_them(
    tmp_path: Path,
) -> None:
    """Composition is the point of inheritance."""
    write_policy(tmp_path / "a.yml", "suppressions:\n  - rule: A\n")
    write_policy(tmp_path / "b.yml", "suppressions:\n  - rule: B\n")
    policy = load_policy(write_policy(tmp_path / "child.yml", "extends: [a.yml, b.yml]\n"))
    assert sorted(rule.rule for rule in policy.rules) == ["A", "B"]


def test_a_baseline_reached_twice_is_loaded_once(tmp_path: Path) -> None:
    """Two policies extending a common baseline is ordinary, not a cycle."""
    write_policy(tmp_path / "base.yml", "suppressions:\n  - rule: SHARED\n")
    write_policy(tmp_path / "left.yml", "extends: base.yml\n")
    write_policy(tmp_path / "right.yml", "extends: base.yml\n")
    policy = load_policy(write_policy(tmp_path / "child.yml", "extends: [left.yml, right.yml]\n"))
    assert [rule.rule for rule in policy.rules] == ["SHARED"]


def test_a_cyclic_inheritance_chain_terminates(tmp_path: Path) -> None:
    """A policy that extends itself must not recurse until the interpreter stops it."""
    write_policy(tmp_path / "a.yml", "extends: b.yml\nsuppressions:\n  - rule: A\n")
    write_policy(tmp_path / "b.yml", "extends: a.yml\nsuppressions:\n  - rule: B\n")
    policy = load_policy(tmp_path / "a.yml")
    assert sorted(rule.rule for rule in policy.rules) == ["A", "B"]


def test_a_parent_is_resolved_relative_to_the_file_that_names_it(
    tmp_path: Path,
) -> None:
    """A shared baseline can sit outside the repository being scanned."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "repo").mkdir()
    write_policy(tmp_path / "shared" / "base.yml", "suppressions:\n  - rule: SHARED\n")
    policy = load_policy(write_policy(tmp_path / "repo" / "p.yml", "extends: ../shared/base.yml\n"))
    assert [rule.rule for rule in policy.rules] == ["SHARED"]


def test_a_missing_policy_file_is_an_error(tmp_path: Path) -> None:
    """Scanning without a policy the operator asked for reports accepted findings."""
    with pytest.raises(SuppressionPolicyError, match="Cannot read suppression policy"):
        load_policy(tmp_path / "absent.yml")


def test_a_policy_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    """A list at the top level is a common mistake and must not be read as empty."""
    with pytest.raises(SuppressionPolicyError, match="policy must be a mapping"):
        load_policy(write_policy(tmp_path / "p.yml", "- rule: B602\n"))


def test_a_suppressions_key_that_is_not_a_list_is_rejected(tmp_path: Path) -> None:
    """Silently ignoring it would suppress nothing while appearing configured."""
    with pytest.raises(SuppressionPolicyError, match="'suppressions' must be a list"):
        load_policy(write_policy(tmp_path / "p.yml", "suppressions: B602\n"))


def test_invalid_yaml_reports_the_file(tmp_path: Path) -> None:
    """The error names the file so it can be fixed."""
    with pytest.raises(SuppressionPolicyError, match=re.escape("p.yml")):
        load_policy(write_policy(tmp_path / "p.yml", "suppressions: [unclosed\n"))


def test_an_empty_policy_file_suppresses_nothing(tmp_path: Path) -> None:
    """A placeholder file is valid and inert."""
    policy = load_policy(write_policy(tmp_path / "p.yml", "\n"))
    kept, suppressed = policy.apply([make_normalized_finding()])
    assert (len(kept), len(suppressed)) == (1, 0)


def test_an_empty_policy_object_suppresses_nothing() -> None:
    """The default when no policy is configured."""
    kept, suppressed = empty_policy().apply([make_normalized_finding()])
    assert (len(kept), len(suppressed)) == (1, 0)


def test_a_rule_without_a_fingerprint_matches_by_pattern() -> None:
    """The two matching modes are exclusive; a fingerprint overrides the patterns."""
    rule = SuppressionRule(rule="B602", fingerprint="deadbeef")
    assert rule.matches(make_normalized_finding()) is False
