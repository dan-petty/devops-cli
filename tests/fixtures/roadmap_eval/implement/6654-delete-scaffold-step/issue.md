## Problem

`devops roadmap step scaffold` (`src/devops_cli/roadmap/steps/scaffold.py`, `src/devops_cli/commands/roadmap_step_scaffold.py`) creates the branch of an item on GitHub through the refs API, at the head of main, with no commit (#5499, #5795). No Job, Service row, manifest or workflow runs it: only its CLI registration (`commands/roadmap_step.py`) names it. In the plain issue-branch flow, the first push of `publish` creates the branch (`git push --force-with-lease=refs/heads/<branch>:`).

## Change

Delete the step, its command, its help text, its tests and its documentation. Correct ADR 0021 with a dated line where it names the step.

## Acceptance criteria

- [ ] `devops roadmap step scaffold` no longer exists, and no code, document or spec names it.
- [ ] The other roadmap steps and their tests pass.

## Decision

The owner approved this deletion on 2026-11-21, after an audit of the git use of devops-cli ("Proceed as recommended").


## Source

Source: https://github.com/dan-petty/devops-cli/issues/3702

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Low", "claim.replaced_status": "New"} -->
