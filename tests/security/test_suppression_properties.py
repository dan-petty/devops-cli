"""Properties of suppression-policy evaluation (`security/suppression.py`, #2545)."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from devops_cli.security.normalization import NormalizedFinding
from devops_cli.security.suppression import SuppressionPolicy, SuppressionRule
from tests.support.builders import make_normalized_finding

_TODAY = date(2026, 10, 28)

_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=12)
_paths = st.lists(_names, min_size=1, max_size=3).map("/".join)

findings = st.builds(
    make_normalized_finding,
    tool=_names,
    rule_id=_names,
    severity=st.sampled_from(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]),
    path=_paths,
    line=st.none() | st.integers(min_value=1, max_value=5000),
)

rules = st.builds(
    SuppressionRule,
    rule=st.just("*") | _names,
    paths=st.just(("*",)) | st.tuples(_paths),
    tools=st.just(("*",)) | st.tuples(_names),
    fingerprint=st.none() | st.text(alphabet="0123456789abcdef", min_size=8, max_size=8),
    expires=st.none() | st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)),
)


@given(rule=rules, finding=findings)
def test_an_expired_rule_suppresses_no_finding(
    rule: SuppressionRule, finding: NormalizedFinding
) -> None:
    """A rule whose expiry is before today matches nothing, whatever it names."""
    expired = SuppressionRule(
        rule=rule.rule,
        paths=rule.paths,
        tools=rule.tools,
        fingerprint=rule.fingerprint,
        expires=_TODAY - timedelta(days=1),
    )

    assert expired.matches(finding, today=_TODAY) is False


@given(finding=findings, other=findings)
def test_a_fingerprint_rule_matches_only_the_finding_with_that_fingerprint(
    finding: NormalizedFinding, other: NormalizedFinding
) -> None:
    """A fingerprint alone decides: the tool, rule and path patterns of the rule do not count."""
    rule = SuppressionRule(
        rule="no-such-rule", tools=("no-such-tool",), fingerprint=finding.fingerprint
    )

    assert (
        rule.matches(finding, today=_TODAY),
        rule.matches(other, today=_TODAY),
    ) == (True, other.fingerprint == finding.fingerprint)


@given(finding=findings)
def test_a_rule_of_wildcards_with_no_expiry_suppresses_every_finding(
    finding: NormalizedFinding,
) -> None:
    """The default rule names every tool, rule and path."""
    assert SuppressionRule().matches(finding, today=_TODAY) is True


@given(policy_rules=st.lists(rules, max_size=4), batch=st.lists(findings, max_size=8))
def test_applying_a_policy_loses_and_invents_no_finding(
    policy_rules: list[SuppressionRule], batch: list[NormalizedFinding]
) -> None:
    """Kept and suppressed findings together are the input, each in input order, and each
    suppressed finding carries the first rule that matches it."""
    policy = SuppressionPolicy(rules=policy_rules)

    kept, suppressed = policy.apply(batch, today=_TODAY)

    suppressed_ids = {id(finding) for finding, _ in suppressed}
    assert (
        kept,
        [finding for finding, _ in suppressed],
        [rule for _, rule in suppressed],
    ) == (
        [finding for finding in batch if id(finding) not in suppressed_ids],
        [finding for finding in batch if id(finding) in suppressed_ids],
        [policy.suppresses(finding, today=_TODAY) for finding, _ in suppressed],
    )
    assert len(kept) + len(suppressed) == len(batch)
