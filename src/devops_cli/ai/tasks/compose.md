## Synthesis Task

You are consolidating the outputs of a multi-segment code review into one authoritative
final report. The per-segment findings may overlap, contradict, or complement each other.

## Consolidation Rules

**Deduplicate** — when the same issue appears across multiple segments, keep one finding
with the most specific location, most precise exploit or impact description, and most
actionable fix. Merge all affected locations into that single finding.

**Preserve severity** — retain the highest severity assigned to an issue across segments.
Only demote if a later segment demonstrates the issue is already fully mitigated. Do not
inflate severity without corroborating evidence.

**Preserve specificity** — do not generalize findings that reference an exact file, line,
or function. If the original is specific, the consolidated version must be equally specific.

**Merge by root cause** — two findings with different locations but the same root cause
(e.g. the same unvalidated input pattern in two functions) should be merged into one finding
listing all locations and a single unified fix.

**Exclude speculation** — if a finding is flagged as unverified and no other segment
independently corroborates it, exclude it from the final report.

**No invention** — do not add findings that are not present in the provided input data.

## Output Requirements

Return the consolidated review as a single JSON block in the standard format. The
`recommendation` field must reflect the aggregate severity of confirmed findings:

| Condition | Recommendation |
|-----------|----------------|
| Any CRITICAL finding present | BLOCK |
| Unresolved HIGH findings, no CRITICAL | REQUEST CHANGES |
| Only MEDIUM or LOW findings | REQUEST CHANGES |
| No findings, or only positive observations | APPROVE |

The `summary` field must be a one-paragraph assessment: overall code quality, the most
critical concern (if any), and a clear statement of what must change before merge.

Maintain your persona's voice and editorial judgment throughout the synthesis.
