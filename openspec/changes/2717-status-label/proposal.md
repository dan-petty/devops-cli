# Proposal

## Why

Issue #2717. The `status/*` label of an issue does not follow the work. Only `devops roadmap implement` writes `status/in-progress` and `status/in-review`. A pull request that a person or an agent opens by hand, and a merge, leave the label as it was. Six closed issues (#2694, #2661, #2665, #2664, #2659 and #2657) still hold `status/new`, and one (#2667) holds `status/ready`. A filter on the label then shows work that is done as work that is not started.

## What Changes

- `devops pr create` sets the Status of the item that the new pull request closes to In Progress. `devops pr ready` sets it to In Review. Both read the closing issues of the pull request with the existing `read_closing_issues`, and write with the roadmap store.
- A Status moves forward only. In Progress replaces no Status but New, Ready or none. In Review replaces those and In Progress. A Blocked item stays Blocked, because a person set it. A pull request that closes no open item of its repository changes nothing.
- A failed read or write exits 1 after the pull request is open or ready, and the message says that only the Status is missing.
- The workflow `.github/workflows/clear-status.yml` removes the `status/*` labels of an issue when it closes, by a merge or by a person.
- ADR 0016 now says that a closed issue holds no Status label.
- A consumer observes the labels and the exit code of two commands, so the change carries one spec delta on `roadmap-item-labels`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-labels`: the Status follows the pull request, and a close removes it.

## Impact

- `src/devops_cli/roadmap/pull_status.py` (new), `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `.github/workflows/clear-status.yml` (new), `docs/adr/0016-labels-hold-the-roadmap-items-fields.md`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The fault is real: `devops gh api 'repos/{owner}/{repo}/issues?state=closed'` on 2026-10-30 lists the closed issues named in Why with their labels. A search of `src/` for the Status constants finds writes only in `roadmap/implement_run.py`.
- `closingIssuesReferences` is the field that GitHub itself uses to close issues on a merge, and `read_closing_issues` already reads it for `devops pr check-readiness`. It is filled when the pull request opens.
- The `issues` event with the type `closed` fires for a close by a merge and a close by a person (GitHub documentation, "Events that trigger workflows"). `GITHUB_TOKEN` with `issues: write` can remove a label (`gh issue edit --remove-label`).
- The Service webhook consumer takes the events `issues opened` and `issues reopened` only, and runs the jobs of the roadmap in rounds. A new event there would need a new job and a new lane. A workflow of 20 lines does the work with no Service change.

## Existing Tool Considered

`gh issue edit --remove-label` on a GitHub-hosted runner covers the close, and `read_closing_issues` with `RoadmapStore.set_field` cover the open and the ready. Nothing is built except the 40-line module that applies the forward-only rule. Cost: about 150k tokens of agent work, one session.

The change deletes no code. It removes the sentence of ADR 0016 that said that no workflow sets a label when an issue closes.
