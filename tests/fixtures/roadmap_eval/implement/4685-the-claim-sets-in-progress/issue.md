### Problem or Motivation

`devops pr create` sets the Status In Progress (`_finish_created_pr` in `src/devops_cli/commands/pr.py`). The claim in `devops repos worktrees add` (`_claimed` in `src/devops_cli/commands/repos.py:502`) sets only the owner and agent labels. The iteration lane opens the pull request after a passing gate, so the pull request opens later. Then the Status of the issue is late too, and the issue shows less of the work in progress.

### Proposed Solution & Architectural Design

`devops repos worktrees add` sets In Progress when it claims the issue. `devops pr create` keeps its forward-only set.

### Target Subsystem

SDLC, Git & PR Governance (`src/devops_cli/commands/repos.py`).

### Existing Tool Considered

The existing status labels and the forward-only status set of `devops pr create` cover the need. Cost (estimate): about 60,000 tokens and 1 hour to build, about 2,000 tokens a month to keep.

### Acceptance Criteria

- A test shows `status/in-progress` after the claim.
- A Blocked item stays Blocked.
- The claim does not set In Review back to In Progress.
- A dry run makes no request.

### Dependencies

None.


Source: https://github.com/dan-petty/devops-cli/issues/4667

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
