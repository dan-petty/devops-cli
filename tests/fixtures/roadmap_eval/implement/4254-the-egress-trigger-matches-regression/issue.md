## Problem

The security gate of the stage job matches a trigger word as a plain substring. The word `regression` contains `egress`, so a plan with the word `regression` in a task text needs a `## Security` section.

Evidence: the live run of the stage job on item #4062 (2026-11-09, model Sonnet) ended with this refusal: "The plan matches the security trigger `egress` and has no security text. Add a non-blank `## Security` section to `design.md`." Item #4062 changes a test only, and the plan said "regression". The refusal is a false positive. The model spent its one return on it.

Where: `_matched_security_trigger` in `src/devops_cli/roadmap/stage/stage_change.py` does `word_lower in t.casefold()` for each word of `SECURITY_TRIGGER_WORDS`. The same defect holds for any other word of the list inside a longer word (for example `loosen` in an unrelated word, or `rbac` in a longer token).

## Expected

A trigger word matches only as a whole word (with word boundaries). The word `egress` matches `egress` and `egress policy`, and does not match `regression`. A trigger of more than one word (`admission policy`, `new host`) matches as a whole phrase. The path triggers stay as they are.

## Acceptance criteria

- [ ] A unit test builds a plan whose task text says "add a regression test" and has an empty `security` field. `check_proposal` returns no security problem. Command: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py`. It fails today: the problem names `egress`.
- [ ] A unit test builds a plan whose task text says "egress policy" and has an empty `security` field. The problem names `egress`. The test passes today and must still pass.
- [ ] The golden set of the stage eval still passes. Command: `uv run devops roadmap eval stage --replay`.

## Existing tool considered

The standard library `re` with `\b` and `re.escape`. No new library and no new helper beyond one compiled pattern.

## Cost

- Tokens to build: low (one pattern, two tests).
- Tokens to keep and to fix: low.
- Elapsed time: about 30 minutes.

## Related

#4204, #4170, #3529 (the stage job and its gates). #3247 (the security trigger).


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
