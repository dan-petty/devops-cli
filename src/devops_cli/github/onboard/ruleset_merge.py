"""The merge of a live GitHub ruleset into the baseline ruleset of row 10 of `devops repos onboard`.

The row writes the baseline ruleset of `github/repository.yaml` over the live ruleset, so the merge
keeps each live rule, each live check entry and each live parameter whose value is stricter than
the baseline value or that its table does not rank. It writes the baseline value only where the
live value is weaker, it adds each baseline rule and parameter, and it gives one warning line for
each setting that it keeps, so the row names a setting that only the owner may lower (rule 5 of
`AGENTS.md`, #7326).
"""

from __future__ import annotations

import copy
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Final

# The parameter of the required checks rule that names each check of a pull request.
_CHECK_ENTRIES: Final[str] = "required_status_checks"
# The parameter of the code scanning rule that names a threshold for each tool.
_SCANNING_TOOLS: Final[str] = "code_scanning_tools"
# The name of the tool in an entry of `code_scanning_tools`.
_TOOL_NAME: Final[str] = "tool"
# The order of the named values of a parameter, weakest first, so a later value of the table admits
# more findings and enforces more. GitHub gives no order to these names, so a text comparison would
# keep `high_or_higher` over `medium_or_higher`, which admits fewer alerts. A value that no table
# ranks stays, so a parameter that GitHub adds is never lowered. Each table holds each value of
# the parameter in the REST API (https://docs.github.com/en/rest/repos/rules).
_VALUE_ORDER: Final[dict[str, tuple[str, ...]]] = {
    "severity": ("errors", "warnings", "notes", "all"),
    "security_alerts_threshold": (
        "none",
        "critical",
        "high_or_higher",
        "medium_or_higher",
        "all",
    ),
    "alerts_threshold": ("none", "errors", "errors_and_warnings", "all"),
}
# The stricter value of each parameter that the order table does not name: a number names its
# direction (`higher` or `lower`), and a boolean names the value that enforces more. `false` is the
# stricter value of `do_not_enforce_on_create`: a true value enforces fewer checks on a branch
# creation.
_STRICTER_WHEN: Final[dict[str, bool | str]] = {
    "minimum_coverage": "higher",
    "max_coverage_drop": "lower",
    "required_approving_review_count": "higher",
    "do_not_enforce_on_create": False,
    "dismiss_stale_reviews_on_push": True,
    "require_code_owner_review": True,
    "require_last_push_approval": True,
    "required_review_thread_resolution": True,
    "strict_required_status_checks_policy": True,
}


def _is_number(value: Any) -> bool:
    """Whether a value is a number of a parameter, and no boolean."""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _rank(parameter: str, value: Any) -> float | None:
    """The rank of a value of a parameter, where a larger rank is the stricter value, or None when
    no table ranks the value."""
    order = _VALUE_ORDER.get(parameter)
    if order is not None:
        return float(order.index(value)) if value in order else None
    direction = _STRICTER_WHEN.get(parameter)
    if isinstance(direction, bool) and isinstance(value, bool):
        return float(value is direction)
    if isinstance(direction, str) and _is_number(value):
        return float(value) if direction == "higher" else -float(value)
    return None


def _stricter(parameter: str, live: Any, base: Any) -> bool | None:
    """Whether the live value of a parameter is stricter than the baseline value, or None when no
    table ranks the two values."""
    live_rank, base_rank = _rank(parameter, live), _rank(parameter, base)
    if live_rank is None or base_rank is None:
        return None
    return live_rank > base_rank


def _value_text(value: Any) -> str:
    """The text of a value of a rule parameter, with the `true` and `false` of the API."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return ", ".join(_value_text(item) for item in value) or "none"
    return str(value)


def _kept_setting_line(rule: str, parameter: str, value: Any) -> str:
    """The warning line of a live setting that the merge keeps: its rule, its parameter and the
    value that the baseline does not hold or holds weaker."""
    return f"keeps {rule}.{parameter} {_value_text(value)}"


def _kept_rule_line(rule: str) -> str:
    """The warning line of a live rule that holds no parameter and that the baseline lacks."""
    return f"keeps the rule {rule}"


def _is_check_entries(rule: str, parameter: str, check_rule: str) -> bool:
    """Whether a parameter of a rule is the check entries of the required checks rule. The change
    line of the row names each required check, so such a parameter gets no warning line."""
    return rule == check_rule and parameter == _CHECK_ENTRIES


def _union_checks(base: Any, live: Any) -> list[dict[str, Any]]:
    """Each check entry of the baseline and of the live rule, once for each context, in name
    order. A baseline entry keeps its details, so no source removes a check."""
    by_context: dict[str, dict[str, Any]] = {}
    for entry in [*(base or []), *(live or [])]:
        by_context.setdefault(str(entry.get("context")), copy.deepcopy(dict(entry)))
    return [by_context[context] for context in sorted(by_context)]


def _merge_tools(
    rule: str, base: Sequence[Mapping[str, Any]], live: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """The scanning tools of the baseline and of the live rule, one entry for each tool name: the
    live threshold where it is stricter or unranked, the baseline threshold where it is weaker,
    and each tool that only one side holds."""
    tools: dict[str, dict[str, Any]] = {
        str(tool.get(_TOOL_NAME)): copy.deepcopy(dict(tool)) for tool in base
    }
    kept: list[str] = []
    for tool in live:
        name = str(tool.get(_TOOL_NAME))
        if name not in tools:
            tools[name] = copy.deepcopy(dict(tool))
            kept.extend(
                _kept_setting_line(rule, f"{_SCANNING_TOOLS}.{name}.{parameter}", value)
                for parameter, value in tool.items()
                if parameter != _TOOL_NAME
            )
            continue
        merged = tools[name]
        for parameter, value in tool.items():
            if parameter == _TOOL_NAME or value == merged.get(parameter):
                continue
            if _stricter(parameter, value, merged.get(parameter)) is False:
                continue
            merged[parameter] = copy.deepcopy(value)
            kept.append(_kept_setting_line(rule, f"{_SCANNING_TOOLS}.{name}.{parameter}", value))
    return [tools[name] for name in sorted(tools)], kept


def _merge_parameters(
    rule: str, base: Mapping[str, Any], live: Mapping[str, Any], check_rule: str
) -> tuple[dict[str, Any], list[str]]:
    """Each parameter of the live rule of `rule`, and one warning line for each kept setting.

    A parameter that the baseline lacks stays. A parameter that both hold keeps the live value
    where it is stricter than the baseline value or where no table ranks the two, and it keeps the
    baseline value where the live value is weaker. The check entries of the required checks rule
    are a union by `context`, and they give no warning line.
    """
    merged = copy.deepcopy(dict(base))
    kept: list[str] = []
    for parameter, value in live.items():
        if _is_check_entries(rule, parameter, check_rule):
            merged[parameter] = _union_checks(base.get(parameter), value)
            continue
        if parameter == _SCANNING_TOOLS and isinstance(value, list):
            tools, lines = _merge_tools(rule, base.get(parameter) or [], value)
            merged[parameter] = tools
            kept.extend(lines)
            continue
        if parameter not in base:
            merged[parameter] = copy.deepcopy(value)
            kept.append(_kept_setting_line(rule, parameter, value))
            continue
        if value == base[parameter]:
            continue
        if _stricter(parameter, value, base[parameter]) is False:
            continue
        merged[parameter] = copy.deepcopy(value)
        kept.append(_kept_setting_line(rule, parameter, value))
    return merged, kept


def _add_live_rule(merged: dict[str, Any], rule: Mapping[str, Any], check_rule: str) -> list[str]:
    """Add a live rule that the baseline lacks to `merged`, and give the warning lines of its
    parameters, or of the rule itself when it holds none."""
    added = copy.deepcopy(dict(rule))
    parameters, lines = _merge_parameters(
        str(rule.get("type")), {}, rule.get("parameters") or {}, check_rule
    )
    if parameters or "parameters" in rule:
        added["parameters"] = parameters
    merged["rules"].append(added)
    return lines or [_kept_rule_line(str(rule.get("type")))]


def _without_file_parameters(
    rule: Mapping[str, Any], check_rule: str, file_parameters: Collection[str]
) -> Mapping[str, Any]:
    """A live rule without each parameter that the settings file of the repository sets, when the
    rule is the required checks rule. The file wins such a parameter (#7423), so the merge keeps
    no live value of it and gives it no warning line."""
    if str(rule.get("type")) != check_rule or "parameters" not in rule or not file_parameters:
        return rule
    parameters = rule.get("parameters") or {}
    return {
        **rule,
        "parameters": {
            key: value for key, value in parameters.items() if key not in file_parameters
        },
    }


def merge_live_ruleset(
    desired: dict[str, Any],
    live: dict[str, Any] | None,
    check_rule: str,
    file_parameters: Collection[str] = (),
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """`desired` with each rule and each parameter of the live ruleset that is stricter than the
    baseline value or that no table ranks, and one warning line for each kept setting.

    `check_rule` is the type of the required checks rule. Its entries are a union by `context`, so
    each live check stays and each baseline check is added. A live value that is weaker than the
    baseline value takes the baseline value, so the baseline raises a weaker live setting and never
    lowers a stricter one (#7326). `file_parameters` names each parameter of the required checks
    rule that the settings file of the repository sets: the caller writes the file value, so the
    merge keeps no live value of it. The merge reads and writes no network: the caller gives both
    bodies.
    """
    merged = copy.deepcopy(desired)
    merged.setdefault("rules", [])
    rules: list[dict[str, Any]] = merged["rules"]
    by_type = {str(rule.get("type")): rule for rule in rules}
    kept: list[str] = []
    for live_rule in (live or {}).get("rules") or []:
        rule = _without_file_parameters(live_rule, check_rule, file_parameters)
        kind = str(rule.get("type"))
        base = by_type.get(kind)
        if base is None:
            kept.extend(_add_live_rule(merged, rule, check_rule))
            by_type[kind] = rules[-1]
            continue
        parameters, lines = _merge_parameters(
            kind, base.get("parameters") or {}, rule.get("parameters") or {}, check_rule
        )
        if parameters or "parameters" in base:
            base["parameters"] = parameters
        kept.extend(lines)
    return merged, tuple(kept)


__all__ = ["merge_live_ruleset"]
