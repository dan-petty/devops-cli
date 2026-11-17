# Design

## Decisions
- A separate rule at the end of the package rules, not a change of the existing SearXNG rule: a later rule wins, so SearXNG leaves `container images`, and the existing rule stays free for PR #6069.
- The rule sets the approval for each update type. The person approves the tag on the Dashboard when they can run the live check.
- The rule stays in `.github/renovate.json`, not in the shared preset, because only this repository runs SearXNG.
- The Monday schedule of the preset for SearXNG stays. An approval made on another day can wait until the next Monday.
- No test reads the new rule (owner, 2026-11-16, #6060); `renovate-config-validator` checks the form.

## Rejected alternatives
- Only the own group, with no approval: a SearXNG pull request would open each Monday and wait for a person.
- `groupName: null` to ungroup: the schema names a string, and a named group gives a short, stable branch name.
