# Proposal: Refine looks again at a wait that older rules set

## Why
Since #3632, a proposal that fails a form check, or that keeps an open question with no "(a person decides)" mark, is a job failure. Before #3632, such a proposal made the item wait on a person. #3632 kept these old waits: refine looks again at a person wait only after a reply, a body edit, a change to a named issue or file, or `--item`. On 2026-11-11, 18 New items still waited on a person for a form failure, and 41 of the 50 person waits from before #3632 hold no "(a person decides)" question. The current rules would not hold them. Closes #4795.

## What Changes
- Add `CONST_ROADMAP_REFINE_RULES_SINCE`, the version of the rules that set the next step of refine. The version is the time from which the rules hold: the release of the rules of #3632 (0.72.0, 2026-11-06T19:25:37Z).
- A round that writes a proposal records the version in the job record as `refine.rules`.
- A wait on a person ends, with no reply and no body edit, when older rules set it: the record holds an older version, or it holds no version and refine's last comment is older than the version.
- A pull request that changes a rule that sets a next step sets a later time in the constant.

## Capabilities
- Modified: `roadmap-refine`.

## Impact
After the release, each round takes up to its limit of the old person waits again, once each. In the census of 2026-11-11 that is 50 of the 96 person waits: the 18 form failures and the other waits from before #3632. A new proposal that fails a form check is a job failure (`retry`, then `failed`), so the item leaves the inbox class `refine`. A new proposal that asks a person again writes one new comment and records the current version, so later rounds keep the wait with no model call. The 46 waits that the current rules set get no new round.

## Feasibility
Checked on the code of `origin/main` (0.113.0). `_still_waiting` in `src/devops_cli/roadmap/refine/refine.py` keeps a recorded `person` step until a reply, a body edit or a change to a named issue or file. The proposal of #3632 (`openspec/changes/archive/2026-11-06-3632-refine-job-failure/proposal.md`) states that the existing waits stay and that a one-time action for them is a separate item. The census of 2026-11-11 gives 96 New items with the step `person`. 50 have a `refine.commented_at` before 2026-11-06T19:25:37Z. The release 0.72.0 holds the rules of #3632, and no person wait has a comment time between 2026-11-06T14:40Z and 2026-11-07T00:17Z, so the cut is clear. Every round that records `person` writes a comment, so the comment time dates the rules of each record that holds no version. The premise holds.

## Existing Tool Considered
No tool covers a job record of this project: the record is a block of the issue body (ADR 0001). Cost to build: about 50,000 tokens and 1.5 hours; to keep: one constant to change with each rule change. The change deletes no code.
