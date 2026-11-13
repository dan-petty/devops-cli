"""The findings of the stage gates: each problem of a refused reply with its gate and code (#4846).

A gate writes each problem from a template of `MESSAGES.roadmap` whose key starts with `stage_`.
The code of a problem is the key of the template that the whole text matches: the standard parser
of format strings (`string.Formatter.parse`) gives the literal text and the fields of each
template, and each field matches any text. When two templates match, the template with more
literal text is the code. A template with less than `_LEAST_LITERAL` characters of literal text,
such as `{reference}`, matches almost any text, so it gives no code. A text that no template
matches has the code `uncoded`. A refusal that no gate of `check_gates` makes has the code of its
check, which is also its gate: `title`, `body`, `validate` or `plan-check` (#4725).

`return_counts` compares the findings of a refused reply with the findings of the next reply. A
finding stays (it is stuck) when the next reply has a finding with the same gate and the same
normalised text: the digits masked and the spaces joined, so a finding that moves to another
group number is the same finding.

`stage_finding_classes.json` holds, for each code of the saved refused replies, its gate, its fix
class and its seed fix rate: the findings that the next reply did not have, the findings that had
a next reply, and the Wilson lower bound of the rate. `finding_classes` makes that file from the
replies.

`gate_extension` is the rule of the extra return of a reply that the checks refuse at the last
gate return (#4851). It reads the findings of the last two refused replies and the fix classes, and
it makes no model call.
"""

from __future__ import annotations

import dataclasses
import re
import string
from collections import Counter
from enum import StrEnum
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from devops_cli.roadmap.stage.stage_change import ProposalGate

CLASSES_FILE: Final[Path] = Path(__file__).with_name("stage_finding_classes.json")
UNCODED: Final[str] = "uncoded"
# The gates of the refusals that `check_gates` does not make; each is also the code of its finding.
TITLE_GATE: Final[str] = "title"
BODY_GATE: Final[str] = "body"
VALIDATE_GATE: Final[str] = "validate"
# The rules of `devops roadmap plan-check` that the job runs before the push (#4725).
PLAN_CHECK_GATE: Final[str] = "plan-check"
# A template needs this many characters of literal text to give a code.
_LEAST_LITERAL: Final[int] = 12
_TEMPLATE_PREFIX: Final[str] = "stage_"
_PATH_FIELD: Final[str] = "path"
_SPACES: Final[re.Pattern[str]] = re.compile(r"(\s+)")
_DIGITS: Final[re.Pattern[str]] = re.compile(r"\d+")
# Fewer samples than this give a code the class `model_fixable`: the job returns such a reply
# today, so the seed changes nothing until the history holds enough cases.
_LEAST_SAMPLES: Final[int] = 5
# The fix rate of a `model_fixable` code: the Wilson lower bound at the confidence 1 - _ALPHA.
_FIXABLE_LOWER: Final[float] = 0.5
_ALPHA: Final[float] = 0.05
_DECIMALS: Final[int] = 3


class FixClass(StrEnum):
    """What a fix of a finding needs. `mechanical`: one edit that the message names in full, with
    no model. `model_fixable` and `low_share`: a return to the model, whose seed fix rate is high
    or low. `never`: the saved returns fixed none."""

    MECHANICAL = "mechanical"
    MODEL_FIXABLE = "model_fixable"
    LOW_SHARE = "low_share"
    NEVER = "never"


# The codes whose message names the one edit that fixes the finding and the text to add.
_MECHANICAL: Final[frozenset[str]] = frozenset(
    {
        "stage_problem_dependencies",
        "stage_problem_missing_module_test",
        "stage_problem_missing_perimeter_test",
    }
)


class StageFinding(BaseModel):
    """One problem of a refused reply: the gate that found it, the code of its message, the path
    that it names (the `{path}` field of the template), and its text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate: str
    code: str
    path: str | None = None
    text: str

    @property
    def key(self) -> tuple[str, str]:
        """The gate and the normalised text: two findings with the same key are the same."""
        return self.gate, " ".join(_DIGITS.sub("#", self.text).split())


class ReturnCounts(NamedTuple):
    """The findings of a refused reply (`before`), those that the next reply does not have
    (`gone`), those that it has again (`stuck`), and its other findings (`new`)."""

    before: int
    gone: int
    stuck: int
    new: int


class FixCount(NamedTuple):
    """The findings of one code that the next reply did not have, of `n` that had a next reply."""

    fixed: int
    n: int


class CodeSeed(BaseModel):
    """The gate, the fix class and the seed fix rate of one code, with its Wilson lower bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate: str
    fix_class: FixClass
    fixed: int
    n: int
    rate: float
    lower: float


class FindingClasses(BaseModel):
    """The seed of each code: the content of `stage_finding_classes.json`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    least_samples: int
    codes: dict[str, CodeSeed]


class _Template(NamedTuple):
    key: str
    pattern: re.Pattern[str]
    literal: int
    anchor: str
    path_group: int | None


def _literal_pattern(text: str) -> str:
    """`text` as a pattern in which each run of white space matches any white space, or none."""
    return "".join(r"\s*" if part.isspace() else re.escape(part) for part in _SPACES.split(text))


def _template(key: str, text: str) -> _Template | None:
    """The pattern of the template `text`, or None when it has too little literal text."""
    try:
        parsed = list(string.Formatter().parse(text))
    except ValueError:
        return None
    literals = [literal for literal, _, _, _ in parsed]
    literal = sum(len(piece.strip()) for piece in literals)
    if literal < _LEAST_LITERAL:
        return None
    fields = [field for _, field, _, _ in parsed if field is not None]
    pattern = "".join(
        _literal_pattern(piece) + ("(.*?)" if field is not None else "")
        for piece, field, _, _ in parsed
    )
    anchor = max((word for piece in literals for word in piece.split()), key=len)
    path_group = fields.index(_PATH_FIELD) + 1 if _PATH_FIELD in fields else None
    return _Template(key, re.compile(pattern, re.DOTALL), literal, anchor, path_group)


@cache
def _templates() -> tuple[_Template, ...]:
    """The templates of `MESSAGES.roadmap` whose key starts with `stage_`, in the catalog order."""
    texts = (
        (item.name, getattr(MESSAGES.roadmap, item.name))
        for item in dataclasses.fields(MESSAGES.roadmap)
        if item.name.startswith(_TEMPLATE_PREFIX)
    )
    found = (_template(key, text) for key, text in texts if isinstance(text, str))
    return tuple(template for template in found if template is not None)


def reset_template_cache() -> None:
    """Forget the compiled templates, so the next finding compiles them from `MESSAGES` again."""
    _templates.cache_clear()


def stage_finding(gate: str, text: str) -> StageFinding:
    """The finding of the gate `gate` for the problem `text`, with the code of its template."""
    stripped = text.strip()
    best: tuple[_Template, re.Match[str]] | None = None
    for template in _templates():
        if template.anchor not in stripped:
            continue
        match = template.pattern.fullmatch(stripped)
        if match and (best is None or template.literal > best[0].literal):
            best = template, match
    if best is None:
        return StageFinding(gate=gate, code=UNCODED, text=text)
    template, match = best
    path = match.group(template.path_group) if template.path_group else None
    return StageFinding(gate=gate, code=template.key, path=path, text=text)


def gate_findings(found: Mapping[ProposalGate, Sequence[str]]) -> list[StageFinding]:
    """The findings of `check_gates`, in the order of its gates and of their problems."""
    return [stage_finding(gate.value, text) for gate, texts in found.items() for text in texts]


def check_findings(gate: str, texts: Iterable[str]) -> list[StageFinding]:
    """The findings of a check outside `check_gates`: each has the code `gate`."""
    return [StageFinding(gate=gate, code=gate, text=text) for text in texts]


def return_counts(before: Sequence[StageFinding], after: Sequence[StageFinding]) -> ReturnCounts:
    """How the findings of a refused reply changed in the next reply, by gate and normalised text."""
    stuck = sum((Counter(f.key for f in before) & Counter(f.key for f in after)).values())
    return ReturnCounts(len(before), len(before) - stuck, stuck, len(after) - stuck)


def fix_counts(replies: Sequence[Sequence[StageFinding]]) -> dict[str, FixCount]:
    """For each code, the findings of each reply that the next reply of the same plan did not
    have, of all the findings that had a next reply. The last reply counts for nothing."""
    fixed: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    for before, after in pairwise(replies):
        left = Counter(f.key for f in after)
        for finding in before:
            seen[finding.code] += 1
            if left[finding.key]:
                left[finding.key] -= 1
            else:
                fixed[finding.code] += 1
    return {code: FixCount(fixed[code], n) for code, n in sorted(seen.items())}


def wilson_lower(count: FixCount) -> float:
    """The Wilson lower bound of the fix rate of `count`, at the confidence 1 - `_ALPHA`."""
    from statsmodels.stats.proportion import proportion_confint

    lower, _ = proportion_confint(count.fixed, count.n, alpha=_ALPHA, method="wilson")
    return round(float(lower), _DECIMALS)


def fix_class(code: str, count: FixCount, lower: float) -> FixClass:
    """The class of `code` from its seed: `mechanical` for a code of `_MECHANICAL`, and
    `model_fixable` for fewer than `_LEAST_SAMPLES` samples. Then `never` when no return fixed it,
    `model_fixable` when the lower bound reaches `_FIXABLE_LOWER`, and else `low_share`."""
    if code in _MECHANICAL:
        return FixClass.MECHANICAL
    if count.n < _LEAST_SAMPLES:
        return FixClass.MODEL_FIXABLE
    if count.fixed == 0:
        return FixClass.NEVER
    return FixClass.MODEL_FIXABLE if lower >= _FIXABLE_LOWER else FixClass.LOW_SHARE


def finding_classes(plans: Iterable[Sequence[Sequence[StageFinding]]]) -> FindingClasses:
    """The seed of each code from the refused replies of `plans`, each plan a list of replies."""
    counts: dict[str, list[int]] = {}
    gates: dict[str, str] = {}
    for replies in plans:
        for reply in replies:
            gates.update((f.code, f.gate) for f in reply)
        for code, count in fix_counts(replies).items():
            total = counts.setdefault(code, [0, 0])
            total[0] += count.fixed
            total[1] += count.n
    codes: dict[str, CodeSeed] = {}
    for code, (fixed, n) in sorted(counts.items()):
        count = FixCount(fixed, n)
        lower = wilson_lower(count)
        codes[code] = CodeSeed(
            gate=gates[code],
            fix_class=fix_class(code, count, lower),
            fixed=fixed,
            n=n,
            rate=round(fixed / n, _DECIMALS),
            lower=lower,
        )
    return FindingClasses(least_samples=_LEAST_SAMPLES, codes=codes)


def load_finding_classes(path: Path = CLASSES_FILE) -> FindingClasses:
    """The seed of each code, from `stage_finding_classes.json`."""
    return FindingClasses.model_validate_json(path.read_text(encoding="utf-8"))


class GateExtension(StrEnum):
    """The decision at the last gate return of a refused reply (#4851). `extended` gives the reply
    one more return. Each other value names the stop: `used` (the item used its extra returns),
    `first` (no reply before it to compare), `stuck` (a finding of the reply before stays) and
    `never` (a finding has a code that no saved return fixed). The value is a label of the
    metric."""

    EXTENDED = "extended"
    USED = "used"
    FIRST = "first"
    STUCK = "stuck"
    NEVER = "never"


class ExtensionEnd(StrEnum):
    """How the extra return of a reply ended (#4851): the checks judged its reply (`passed` or
    `refused`), or the run ended before that (`ended`). The value is a label of the metric."""

    PASSED = "passed"
    REFUSED = "refused"
    ENDED = "ended"


class ExtensionDecision(NamedTuple):
    """The decision of `gate_extension`: the result, the gates of the findings that stop the
    reply, and the count of the findings of the last reply with the fix class `never`."""

    result: GateExtension
    gates: tuple[str, ...] = ()
    never: int = 0


def gate_extension(
    before: Sequence[StageFinding] | None,
    after: Sequence[StageFinding],
    *,
    used: int,
    classes: FindingClasses,
) -> ExtensionDecision:
    """Whether a reply that the checks refused at the last gate return gets one more return. The
    guard comes first: an item that used `CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS` extra
    returns gets no other. Then the rule reads the findings of the reply before (`before`, None
    when no return compares two replies) and of the last reply (`after`): no finding of `before`
    stays, and no finding of `after` has the fix class `never` in `classes`. With no finding that
    stays, each finding of the reply before is gone. A code that `classes` does not hold is no
    `never` code. The rule makes no model call."""
    never = [
        finding
        for finding in after
        if (seed := classes.codes.get(finding.code)) is not None
        and seed.fix_class is FixClass.NEVER
    ]
    if used >= CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS:
        return ExtensionDecision(GateExtension.USED, never=len(never))
    if before is None:
        return ExtensionDecision(GateExtension.FIRST, never=len(never))
    kept = {finding.key for finding in before}
    stuck = sorted({finding.gate for finding in after if finding.key in kept})
    if stuck:
        return ExtensionDecision(GateExtension.STUCK, tuple(stuck), len(never))
    if never:
        gates = tuple(sorted({finding.gate for finding in never}))
        return ExtensionDecision(GateExtension.NEVER, gates, len(never))
    return ExtensionDecision(GateExtension.EXTENDED)


__all__ = [
    "BODY_GATE",
    "CLASSES_FILE",
    "PLAN_CHECK_GATE",
    "TITLE_GATE",
    "UNCODED",
    "VALIDATE_GATE",
    "CodeSeed",
    "ExtensionDecision",
    "ExtensionEnd",
    "FindingClasses",
    "FixClass",
    "FixCount",
    "GateExtension",
    "ReturnCounts",
    "StageFinding",
    "check_findings",
    "finding_classes",
    "fix_class",
    "fix_counts",
    "gate_extension",
    "gate_findings",
    "load_finding_classes",
    "reset_template_cache",
    "return_counts",
    "stage_finding",
    "wilson_lower",
]
