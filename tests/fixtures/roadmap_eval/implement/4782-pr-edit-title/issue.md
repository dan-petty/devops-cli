### Problem or Motivation

`devops pr create` checks the title with `title_problems` (`src/devops_cli/commands/pr.py`). Agent title failures fell from 41 to 2 after that check came (#3213). `devops pr edit --title` (`edit_pr` in the same file) has no check, so an edit can still set a title that the `PR Title` check refuses.

A commit-msg hook is not an option. `CONTRIBUTING.md` decides that no hook checks branch commits. In a test, a commit-msg hook refused the `wip:` commits of the Job, merge commits and `fixup!` commits.

### Proposed Solution & Architectural Design

In `edit_pr`, when `--title` is given, run `title_problems` with the declared labels. Refuse with the same message as `create`.

### Target Subsystem

SDLC, Git & PR Governance (`src/devops_cli/commands/pr.py`).

### Existing Tool Considered

The repository's own `title_problems` covers the length, scope and `!` rules in 0.41 s. conventional-pre-commit 4.5.0 and commitizen 4.19.3 both accepted a title with `!` and a 68-character summary, so they do not cover the rules. Cost (estimate): about 10 lines and 1 test, about 20,000 tokens and half an hour.

### Acceptance Criteria

- Tests: `devops pr edit --title` refuses a title with `!` and a title with a 61-character summary, and it accepts a valid title.
- In the 14 days after the merge, at most 2 agent pull request title failures.

### Dependencies

None.


Source: https://github.com/dan-petty/devops-cli/issues/4771

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "intake.jev_shadow": "{\"at\":\"2026-11-11T19:34:05Z\",\"answers\":{\"priority\":[\"P1-High\",0.53,\"P2-Medium\"],\"value\":[\"High\",0.26,\"Medium\"],\"effort\":[\"Low\",0.98,\"Low\"],\"duplicate\":[\"\",0.08,\"\"]}}"} -->
