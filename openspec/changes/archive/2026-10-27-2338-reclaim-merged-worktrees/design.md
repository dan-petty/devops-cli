# Design

## Context

See proposal.md for the motivation and the evidence.

- `prune_worktrees` in `src/devops_cli/git/worktree_inventory.py` decides every worktree before it removes any: local state first (`_decided_by_local_state`: main, forced, locked, directory missing, dirty), then one `GET /repos/{repo}/commits/{sha}/pulls` for each worktree that local state does not decide (`_decide`). A failed GitHub read ends the run with nothing removed. `plan_prune` is its dry run and lists the requests.
- `devops repos worktrees add` (`src/devops_cli/git/worktree_add.py`) checks the branch form, reads the local worktrees for a holder, reads `origin` for a holder, fetches and creates.
- `WorktreeEntry`, `WorktreePruneItem` and `WorktreePruneReport` are pydantic models. The report of `add` is `WorktreeAddReport`.
- `get_repo_origin_name` reads `git remote get-url origin` and returns `owner/repo`; `prune` uses it as the repository whose pull requests it reads.

## Goals / Non-Goals

**Goals:**

- Merged worktrees leave the disk without a person running `prune`, in the agent workflow as it is: every piece of work starts with `add`.
- A merged worktree never blocks the issue it was made for.
- `prune` and the reclaim never remove the directory a shell is in.
- A person sees how much each removal frees.

**Non-Goals:**

- No scheduler, no background process and no hook of git. Nothing runs unless a person or an agent runs `add` or `prune`.
- No new rule for what is removable. The reclaim and `prune` share one decision function.
- No removal of local branches. A branch costs bytes, not gigabytes, and `add` already ignores a local branch with no worktree.
- No grace period after a merge. See the risks.

## Decisions

**The trigger is `add`, before the check for a holder.** The proposal lists the four other places and why each fails. `add` is the first command of every piece of work (CONTRIBUTING.md, SDLC.md), so the cleanup runs as often as work starts, and it clears every worktree of the repository, whatever agent tool made it, because `git worktree list` names them all. It runs before the check for a holder because a merged worktree holds its issue: `add 2344` is refused today for that reason. Alternatives rejected: a separate command that a routine calls (it is `prune` again, and nobody runs it), and a hook on `devops pr` (the merge happens after the agent's commands end).

**The reclaim calls `prune_worktrees(confirm=True)`.** One rule set decides what is removable, so the two commands cannot disagree. Alternative rejected: a second, lighter rule in `add` that reads only `git branch --merged`. This repository squash-merges, and a squash never makes the branch tip an ancestor of `main` (the proposal of the archived change 2341-worktrees-prune-merged-pr), so the lighter rule would keep every squash-merged worktree.

**A failed reclaim is reported and the run goes on.** `add` catches `DevOpsCLIError` from the reclaim, puts its message in `reclaim_error`, prints it as a warning and creates the worktree. This is no swallowed error: the reason is in the output and in the JSON. Housekeeping must not block the work it precedes, and the reclaim needs the GitHub API and a token, which `add` itself does not. `prune_worktrees` decides all worktrees before it removes any, so a failed read removes nothing and leaves no half-reclaimed state. Alternative rejected: fail `add` when the reclaim fails. An agent without a token, or offline, could not start work.

**The current directory is guarded in the decision function.** `_decided_by_local_state` gets the resolved current directory and keeps a worktree that holds it, before the `force` rule, so `--force` cannot remove it either. A guard in `prune_worktrees` alone would leave `plan_prune` wrong, and `plan_prune` would list a request for a worktree that is never read. The comparison is `Path.is_relative_to` on resolved paths. The main worktree is refused first, so a current directory in a worktree nested under the main one still names the right worktree.

**Sizes come from a walk before the removal.** `directory_size` walks the directory with `os.walk`, which does not follow links, and sums `lstat` sizes. A real worktree of 46,586 files took 0.38 s. A removed item keeps the size of the directory as it was before the removal, and the reports give the total. Alternative rejected: `du`, which differs between GNU and BSD and starts a process for each worktree.

**`--reclaim/--no-reclaim`, on by default.** An agent that must not read GitHub, such as a test, passes `--no-reclaim`.

**The dry run lists the reclaim's requests and keeps the local check as it is.** `add --dry-run` calls `plan_prune` and puts its requests before the three git commands. The check for a local holder runs on the worktrees as they are, because only a GitHub read can tell that a worktree is merged. So a dry run can refuse an issue that the real run would free by reclaiming its merged worktree. The refusal names the worktree, and the plan lists the read that would settle it.

## Risks / Trade-offs

- [A clean worktree at the head of a merged pull request is still in use by another agent that has not started its next edit] → The removal loses no change: the worktree has no uncommitted path, and its commits are in `main`. Only the directory and its environment go, and `add` makes a new one. The agent that runs the reclaim is protected by the guard for its own directory. A grace period after the merge would protect the others, and needs the merge time, which `get_commit_pulls` gives; it is left out until a case shows the need.
- [`add` reads one pull request for each worktree that local state does not decide] → On this host, a preview of 8 worktrees, with 4 pull request reads, took 4.5 s including the start of the command. After the first reclaim, only the live worktrees remain. `--no-reclaim` skips the reads.
- [The origin name of a repository whose origin is not on GitHub is a made-up `owner/repo`] → `prune` has the same behavior. The read fails, and the failure becomes the warning of `reclaim_error`.
- [Two `add` runs reclaim at once] → Both decide the same worktrees. The second `git worktree remove` fails on a directory that is gone and is reported as `failed` in the reclaim, which becomes the warning. Nothing is removed twice.
