# Design

## Decisions

- **Plain issue-branch flow** (owner decision of 2026-11-21, #3702 comment 7065393209). The phases work the branch as a developer does:
  - `prepare` (App token, no code of the pull request) makes a full clone in a folder that is new to the run, switches to the branch, and records the base and the lease.
  - `agent` (no GitHub credential) rebases, does the work and writes the patches.
  - `publish` (App token, no code of the pull request) applies the patches in a new repository, commits as the bot and pushes with `--force-with-lease`.
- **The base and the lease come from `prepare`.** `prepare` fetches nothing after the clone: the full clone holds the default branch and the pushed branch. The lease is the tip of the pushed branch, or empty for a new branch, which must not exist when `publish` pushes. The base of the patches is the lease when the lease is not empty and the run makes no rebase (`--no-rebase`). In every other case, a new branch too, it is the tip of the default branch. The agent rebases onto that commit and makes no remote call. `publish` takes the base only from the state, never from `outcome.json` or the tree of the agent, and fetches it at depth 1 into its new repository. The full clone makes a merge base sure, so no deepen and no merge-base check is necessary.
- **The archive stays its own commit.** The agent writes `work.patch` up to the commit before the archive commit, and `archive.patch` from there to the head. `publish` writes one commit of the bot for each. A later rebase can then skip the archive commit and archive again.
- **The agent settles the stops of the rebase as a developer does.**
  - `git rebase --skip` for a commit whose every change the run makes again: a file under `openspec/changes/archive/` or `openspec/specs/`, the removal of a file of a change folder, or a generated document. That is an archive commit. The plan commit adds its change folder, so the rule does not skip it, and a conflict there stops the item.
  - `git checkout --ours` and a new generation for conflicts only in the generated documents and `uv.lock`.
  - Any other conflict aborts the rebase and stops the item with the class `conflict`, as before. The model step that settles such a conflict is #6640.
  - The implement job no longer calls `fix_rebase_conflict`.
- **The patch has a fixed format.** `git diff --binary --full-index --no-color --no-ext-diff --no-textconv --src-prefix=a/ --dst-prefix=b/`, so no diff setting of the clone or of the home folder changes it. The implement patches go from commit to commit, so a file that no commit holds is not published, as before.
- **`publish` reads the new tree from its objects.** The folder of the change, `proposal.md` and `tasks.md` come from `git ls-tree` and `git cat-file` of the new commit. The title and the body are built from them and from the facts of the item. The why of the agent is checked again with `safe_text`, `closing_keyword_in` and `build_body`, and the title of the item replaces a why that fails.
- **The marks come at the end.** `publish` writes the record of the run once, from `outcome.json`. A killed Job loses the groups of its run: a run makes no push before `publish`. The live table of `devops roadmap follow` reads `implement.trace` during the run, so it shows no live trace while the agent runs. `roadmap/steps/open.py` reads `implement.checked_sha`, which `publish` writes after the push, as before.
- **A second run pushes nothing.** `publish` pushes no commit when the lease holds the new tree already, and a second `publish` of a run that ended at the draft writes nothing. `prepare` clears `implement.published_sha`, so `publish` takes it as the lease only after its own push.
- **The withdraw goes.** No run pushes before `publish`, so a return to New has no checkpoint to take back. `implement.base`, which only the withdraw read, goes too.
- **Until #3700, git reads no global or system configuration in `prepare` and `publish`.** `--phase all` runs the phases in one container, and an earlier item of the same Job can have run code of a pull request in the home folder. The git calls of the clone and of `publish` set `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` and get the credential helper from `-c` values. `publish` ends the leftover processes once first.
- **The symlink stop of the step stays until #3700.** `publish` refuses a new or changed link, gitlink and `.gitmodules`. The stop in the step keeps a link out of the formatters while the agent and the token share a container.
- **No count line and no new token permissions.** One process mints one token for the three phases in `--phase all`, so the token without `workflows: write` and the count line of the agent container wait for #3700. `publish` refuses a workflow file that the merged plan does not name.
- **fix-checks shares the simple publish.** Its `prepare` clones into the run folder and switches to the head branch, and its `publish` uses the new repository. fix-checks keeps its base and lease, the judged head; its rebase is #6639.

## Rejected alternatives

- Git plumbing (`read-tree`, `apply --cached`, `write-tree`, `commit-tree`) on objects of a second git folder: porcelain in a new repository does the same with less code.
- A push of the rebased branch in `prepare`: the rebase can need the settle of a conflict, which is work of the agent.
- One commit for the whole run: a later rebase would skip the whole item when it skips the archive commit.
- A patch of the working tree with `git add -A` for implement: a file that no commit holds was never published, and the run folder holds no ignore rule of the target.
