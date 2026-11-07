# Design

## Decisions

- **`git reset --soft`, not `--mixed` or `--hard`.** `--soft` moves HEAD only, so the index and the checkout keep the work of the agent, and the later `git add -A` stages it. Rejected: `--mixed`, which also resets the index and leaves the work unstaged; and `--hard`, which deletes the work of the agent, the defect that this change fixes.
- **The reset runs in `_exit_failure`, before `keeper.fold()`.** Every exit check runs it, also the one after an extra turn, which can commit too. Rejected: a reset in `_turn` after the run. It misses the extra turn, and the head check of `_exit_failure` would still stop.
- **The target is `keeper.expected_head`.** It is the tip after the last `wip:` commit, or the base once the keeper folded. The `wip:` commits of the step stay, and `fold` folds them into the commit of the step. Rejected: `keeper.base`, which would discard the `wip:` commits that the step kept.
- **A reset that fails stops the step with `head_moved`.** The reason names the command, the exit status and the output of git, so the stop comment names its cause. Rejected: a second try of the reset. It fails for the same reason, and it adds a path that no check covers.
- **No new class and no new action.** `head_moved` keeps `retry` in `ACTION_BY_CLASS`. The reset makes the class rare, and the meaning of the class is the failed reset.
- **The proof uses real git.** The tests run git in a repository in `tmp_path`. A fake of `git` would show the call and not the state of the history. One test fakes the exit of `git reset --soft` at the process edge, the only way to make git refuse a reset to a commit that exists.

Reads: `src/devops_cli/roadmap/implement_wip.py`, `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_failure_class.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `docs/ROADMAP_WORKFLOW.md`.
