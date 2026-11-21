# Design

## Decisions

- **One run folder, three folders.** `state/` holds the state file that `prepare` writes and `publish` reads; the agent phase does not read it. `work/` holds the clone and `input.json`. `out/` holds `agent.patch`, `outcome.json` and `summary.json`. `--phase all` makes the folder in a temporary folder and removes it.
- **A round that needs no agent ends in `prepare`.** The bounds, the claim, the caps, the plan, the wait of a CI infrastructure failure and the ready path run as before (`judge_round`). The report goes to the state file, and `publish` prints it.
- **No rebase.** The base and the lease are the judged head. The agent phase needs no network git call. The rebase onto `main` comes with implement in part C.
- **The clone holds no credential.** `prepare` clones with the App token, which git gets from its environment for each call. `.git/config` holds no token, no credential helper and no extra header. `add_worktree` puts the worktree in the agent worktree folder of the data folder, as it does for every take-over.
- **The agent reads no store.** `prepare` writes the item to `input.json`, and the model fix reads it there. `run_fix_step` stays the engine; #6527 changes it.
- **The patch comes from a new git folder.** Its objects are the objects of the clone, and it has its own index and configuration. `git add -A` stages every file of the checkout over the base tree, so no clean filter or `core.fsmonitor` of the clone runs.
- **`publish` reads the outputs as data.** `lstat` on the root and on `out/`, `O_NOFOLLOW | O_NONBLOCK`, a regular file and a size limit. The models refuse a key outside the model, and the step takes `result` and `detail` only from its enums. Each text goes through `mask_secrets`; the comment puts the paths in a fenced block.
- **`publish` applies the patch as data.** A fresh clone fetches the branch at depth 1 through `OriginGit`; its tip must be the lease. A second new git folder applies the patch with `git apply --cached` and `git write-tree`. `git diff-tree -r --raw` refuses a new or changed link or gitlink, a change of `.gitmodules` and a workflow file that the plan does not name. `git commit-tree` writes one commit with the bot as author and committer.
- **The claim check runs three times.** In `prepare`, at the start of `publish`, and in `publish` right before the push (`check_preconditions` on the pull request and the item as GitHub holds them then).
- **The token keeps its permissions in B.** One process mints one token for the three phases, so a token without `workflows: write` waits for #3700. In B, `publish` refuses a workflow file that the merged plan does not name.
- **No count line.** `all` prints only the current report. The count line of the agent container waits for #3700.

## Rejected alternatives

- A git bundle from the agent phase: it carries refs, tags, history and authors, so it needs more checks than a patch.
- A refusal of private repositories in `prepare`: `prepare` holds the App key and clones with the token, as the code does now.
- Two orchestrations, one in process and one on files: `--phase all` runs the same three functions on a temporary run folder.
