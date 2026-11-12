# Design

## Decisions

- The gate re-anchors only a unique match. A text on exactly one line of the staged file gives one sure target for a stale line number. A text on two or more lines gives no sure target, so the gate refuses the citation with the current stale-citation problem.
- The match test does not change: the cited text after white space collapses is in the line after white space collapses. So a citation that quotes part of a longer line, which the gate accepts at line `N` today, is also accepted at another line.
- Line `N` wins. When line `N` holds the text, the gate accepts the citation and does not count a re-anchor, also when other lines hold the text.
- The minimum of 3 characters applies first. A short text matches almost any line, so the gate refuses it before it looks at other lines.
- Each citation gets one `_Citation` record: its problem, whether it cites a line, and whether the gate re-anchored it. `_plan_citation_problems` keeps its return type, joins the problems as before and counts the records for the log line. The log line has the count of line citations too, so a person can read the rate from one line.
- The log line is written only when the check has a reader of the staged files. The golden-set replay has no reader and judges no citation, so it writes no line.

## Rejected alternatives

- Refuse as now. The refusal costs one more reply and often fails again, and the text is true at the staged commit.
- Re-anchor the first match or the closest match. The first line is arbitrary, and the distance from the stale line is no evidence of the correct line.
- Fuzzy text distance. It can accept a wrong line and adds a dependency.
- A metric counter or a stage comment for the count. A counter adds telemetry for a diagnostic count, and a comment changes the item comment of the stage job.
