# Proposal: #4685

## Why

`devops pr create` sets the Status In Progress on the issue that its pull request closes (`_finish_created_pr` in `src/devops_cli/commands/pr.py`). The claim in `devops repos worktrees add` (`_claimed` in `src/devops_cli/commands/repos.py`) sets only the label `owner/agent`. An agent can work for a long time before it opens the pull request, and the iteration lane of the Gitea plan opens it only after a passing gate. Until then the issue shows a Status of New, Ready or Planned, so the roadmap shows less of the work in progress. Closes #4685.

## What Changes

- After a claim that is made, `devops repos worktrees add` sets `status/in-progress` on the item when its Status is New, Ready or Planned, or when it has no Status. It keeps every other Status: In Progress, In Review and Blocked. A Blocked item stays Blocked also when the implement job recorded the stop, because a claim is no fix of a stop.
- The forward rule is the one of `devops pr create` (`_REPLACES` in `src/devops_cli/roadmap/pull_status.py`). The new function `set_claimed_status` in that module applies it and writes through the one Status writer, `write_status` (#5018), with the new fact `agent_claimed` of `StatusFacts`, which `derive_status` maps to In Progress. `progress_as_agent` in `src/devops_cli/roadmap/claim.py` calls it and gives the reason of a failed write as text, as `claim_as_agent` does.
- A failed Status write does not stop the command. The JSON report holds the reason in the new field `status_error`, `claimed` stays true, and the table output prints a warning.
- `--dry-run` lists the read and the write of the Status after the requests of the claim, each with its condition, and sends no request.
- `devops pr create` keeps its forward-only set.
- `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROADMAP_WORKFLOW.md` and the help of the command name the new Status write.

## Capabilities

- `repos-worktrees-add`: the claim of the issue for an agent also sets the Status In Progress when the Status moves forward.

## Impact

- An item that an agent starts with `devops repos worktrees add` shows In Progress at once, not only when the pull request opens.
- Each real run makes up to four more GitHub requests after a claim that is made: one read of the issue, then the read and the write of the Status, and the read-back of `write_status`. The run makes no write when the Status stays.
- `devops roadmap claim` does not change: it sets only the owner label.

## Feasibility

- `origin/main` at 310981773: `claim_as_agent` in `src/devops_cli/roadmap/claim.py` writes only `ItemField.OWNER`, and `_claimed` in `src/devops_cli/commands/repos.py` calls nothing else. `set_delivered_status` in `src/devops_cli/roadmap/pull_status.py` writes In Progress when the Status is none, New, Ready or Planned.
- A live claim shows the gap: after `uv run devops roadmap claim 4685 --as agent --confirm`, issue #4685 held `owner/agent` and still `status/new`.
- The new tests fail on `origin/main`: the report has no `status_error`, the item keeps `status/ready`, and the dry run lists no Status write.

## Existing Tool Considered

The existing status labels and the forward-only Status set of `devops pr create` cover the need, and this change reuses that rule. No open tool holds the roadmap labels of this project. Cost (estimate): about 60,000 tokens and 1 hour to build, about 2,000 tokens a month to keep.
