# Design

## Decisions

- **Put the check in a new `devops ci` row `roadmap-stage-eval-commits`, with its code in `tests/gate/roadmap_stage_eval_commits.py`.**: `docs/TESTING.md` says a check of committed files is a row of `devops ci` and a test of `src/` starts no system program, and a row may read the git history.
- **Write the canned-answer test of the row verdict before the check module, in the same behavior group, and register the row in that group too.**: The new behavior is the verdict of the row, so its failing test comes first; the row table, its title and the docs lists must change in the same step, because the row test and the invariant list fail without them.
- **Separate the verdict from the git call: `bad_base_commits` and `outcome` take the shallow flag and a `resolves` callable, and `main` supplies the git answers.**: `docs/TESTING.md` says a test of the logic of a check gives it canned output and starts no program, so the pytest test needs a seam that is no process.
- **Keep `test_each_merge_commit_of_the_set_is_a_full_hash_or_the_case_reads_none` in pytest.**: It reads the loaded cases and no git history, so it starts no program and skips on no host state.
- **Register the row last in the table, after `domain`, and add it last to `_GATE_ROWS`.**: `tests/commands/test_ci_gate_rows.py` holds the gate rows last in the table in the order of that dict.
- **Change the requirement `Each commit of the set is a real commit or the case reads none` in place, with no rename.**: Its name covers both commits of a case, and the new text still requires the merge-commit check and the parity of the two commits, so the name fits the text.

## Rejected alternatives

- **Keep the pytest test and let the shared git fake answer its two commands.**: `docs/TESTING.md` forbids a skip on host state and a check of committed files as a pytest test, and the fake answers a recorded scenario, so it cannot show that the repository holds the old commits that the cases name.
- **Add the check to the `test-tree` row.**: `tests/gate/tree.py` runs checks over the parsed Python trees of `src/` and `tests/`, and it reads no golden case data and no git history.
- **Run `git cat-file` alone and let its failure report the shallow clone.**: A missing object names no shallow clone, and the issue asks for a message that names the missing history, so the row reads `git rev-parse --is-shallow-repository` first.
- **Move the merge-commit hash test to the gate too.**: `test_each_merge_commit_of_the_set_is_a_full_hash_or_the_case_reads_none` reads loaded data and no git history, so it starts no program and breaks no rule of `docs/TESTING.md`.
- **Rename the requirement `Each commit of the set is a real commit or the case reads none` to name the base commit only.**: The text still requires the test to check each merge commit and the parity of the two commits, so the old name fits the new text and a rename would leave a name that fits half of it.
