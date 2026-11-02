# Proposal

## Why

A person learns what a roadmap Job did from `kubectl logs` and one comment at the end, so a running Job is opaque. #3076 asks for one command that shows the live trace of the current run and the history of past runs.

## What Changes

- Add `devops roadmap follow <issue>` in `src/devops_cli/commands/roadmap.py`, which prints the live trace of the Job pod and the recorded history of past runs.
- Add `src/devops_cli/roadmap/follow.py`: it reads the pod log through the Kubernetes client, parses the job record of the issue body, and builds the rows.
- Render every row with the PR comment table renderer, so the header and the column order equal those of the PR comment table.
- Mask every value with the masker that the log lines already use, before it is printed.
- Print the follow command for each item in the output of `devops roadmap inbox` and `devops roadmap explain`.
- Document the command in `docs/roadmap/follow.md`, in `docs/ROADMAP_WORKFLOW.md` and in the CLI reference.
- The change carries a spec delta for the new capability `roadmap-follow`, because a devops command and its output are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-follow`: The command shows a running Job and a finished Job, The command sends at most one GitHub request for the history, The output has the shape of the PR comment table, The output masks secrets, The inbox and explain output names the follow command

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/follow.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`
- Documents: `docs/roadmap/follow.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/roadmap/test_roadmap_follow.py`, `tests/roadmap/test_roadmap_follow_command.py`, `tests/roadmap/test_roadmap_inbox_command.py`, `tests/roadmap/test_roadmap_explain_command.py`

## Feasibility

- `probes` shows that the cited identifiers exist: `inbox` is defined at src/devops_cli/commands/roadmap.py:813:        inbox = read_inbox(store, repo=target, now=datetime.now(UTC))
- `probes` shows the inbox help text: `inbox` is defined at src/devops_cli/lang/en/help.py:1495:    inbox: str = (
- `probes` shows the explain help text: `explain` is defined at src/devops_cli/lang/en/help.py:1429:    explain: str = (
- `probes` shows that `follow` is an option of other groups today and no roadmap command: `follow` is defined at src/devops_cli/commands/argo.py:677 and at src/devops_cli/commands/k8s/cluster_context.py:404. The issue asks for a command to create, so no path was removed.
- `read_file` on `src/devops_cli/commands/roadmap.py` showed the `inbox` and `explain` command bodies that the change extends with the follow line.
- `read_file` on `src/devops_cli/roadmap/inbox.py` and `src/devops_cli/roadmap/explain.py` showed that each builds its rows in one place, so the follow line joins that seam.
- `search_code` found the PR comment table renderer and the log-line masker, which the change reuses instead of adding a second of either.
- First checks against the real system: `uv run devops roadmap follow 3076` against a cluster that holds the runner Job of the item, then `uv run devops ci test tests/roadmap/test_roadmap_follow.py` and `openspec validate --strict`.

## Existing Tool Considered

The Kubernetes Python client (`kubernetes`) is the open, maintained library that reads pod logs and pod state, and `devops_cli.k8s` already wraps it. It covers no job-record parser, no trace rows and no masking, so the change adds about 6,000 tokens of new code, about 1,500 tokens for each later fix, and about one day of work. It deletes no internal code.
