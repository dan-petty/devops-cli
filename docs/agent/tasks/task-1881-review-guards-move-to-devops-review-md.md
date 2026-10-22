# Task: The Review-Only Guards Move From AGENTS.md to .devops/review.md (#1881)

**Issue**: [#1881](https://github.com/dan-petty/devops-cli/issues/1881)
**Scope**: type/docs, scope/docs, scope/ai
**Feasibility**: The author checked this on 2026-10-22. The author read the loader `nearest_review_conventions` in `src/devops_cli/ai/review/review_environment.py` and every caller of it. The author ran the new tests on the base tree, where they failed because the file did not exist. The evidence is in the section "Feasibility Evidence".

## Description

Six bullets in section 5 of `AGENTS.md` tell a review what not to flag. An agent that writes code cannot use them, and they used 1,754 characters of a file with a cap of 40,000. The owner decided on 2026-10-22 that a path-scoped rule file may hold them and that they move word for word.

- **The new file.** `.devops/review.md` holds a title, an intro of two sentences and the six guards. The guards are the text of `AGENTS.md`, copied by a script that located the bullets by their text. The two sub-bullets of "Context-Aware Documentation, Examples & Test Evaluation" keep their parent bullet, so the grouping is the same.
- **The inventory.** `tests/test_docs_inventory.py` requires a class for each Markdown file. `CONST_DOCS_INVENTORY` lists `.devops/review.md` as a prompt, because code loads the file at run time.
- **The pointer.** `AGENTS.md` has one bullet, "Review Guards", in the place of the first guard. It names the file and the loader.
- **What stays.** The bullets "Zero Hallucinated CVEs & Synthetic IDs" and "Internal Infrastructure vs External SSRF Distinction" stay in `AGENTS.md`. The bullet "Closed-Loop Review & Self-Improvement Cycle" stays with its `devops review` examples, which `tests/test_docs_review_loop.py` reads.
- **The tests.** `tests/test_review_project_conventions.py` holds two tests. `test_the_review_conventions_of_this_repository_hold_each_guard_in_full` loads the file through `nearest_review_conventions(REPO_ROOT)` and compares the whole text with a syrupy snapshot. A guard that loses a word fails the test. `test_agents_md_holds_no_review_guard_and_names_the_file_once` takes each guard from the loaded file. It checks that `AGENTS.md` holds none of them and names `.devops/review.md` once. Two negative controls give the same check a file with other text and a text with one guard. A person who edits a guard regenerates the snapshot with `--snapshot-update --snapshot-file-lock`.
- **The wording.** The guards keep their original wording, as the issue requires. The title, the intro and the pointer are in ASD-STE100. A later edit of a guard converts it.

## Feasibility Evidence

- **Loader.** `nearest_review_conventions` reads the plain UTF-8 Markdown file named by `CONST_REVIEW_CONVENTIONS_FILE` (`.devops/review.md`). It walks from the start directory up to the repository root, and the nearest file wins. It refuses a link and strips the text. The file has no front matter and no schema. The file is 1,913 characters. No code enforces a size cap on the file.
- **Size.** `AGENTS.md` had 38,871 characters before the change. It has 37,260 after the change. The change frees 1,611 characters. The cap is 40,000.
- **Red on base.** On the base tree `nearest_review_conventions` returned an empty string. The snapshot test failed because the text did not match the snapshot. The `AGENTS.md` test failed because the loaded file gave no guard. Both tests pass after the change.
- **Mutations.** Each change below makes a test fail. The snapshot test fails when `MUST NOT be reported` becomes `may be reported`. It fails when `does NOT constitute CWE-200` becomes `may constitute CWE-200`. It fails when `MUST NOT be flagged as insecure deserialization` becomes `may be flagged as insecure deserialization`. It fails when the file is removed. The `AGENTS.md` test fails when the base `AGENTS.md` returns or when one guard returns. It fails when the pointer bullet is deleted or when the pointer names the file twice. It fails when the file is removed. A helper that finds no guard fails the control with one guard.
- **No guard lost in a prompt.** A search of `src/devops_cli/ai/tasks/` finds no `NameError`, `CWE-200` or `outputs.tf` text. The task `review.md` there has no `getattr(model, ...)` guard. It only says to check `__getattr__` for a symbol. Its SSRF line is an egress rule and not the exemption for internal connectors. So the guards are not duplicated there. The issue said they were, for part of the set.
- **Count.** The issue says eight bullets and 1,460 characters. The change moves six bullets and 1,754 characters, the text of the bullets on the base tree.
- **Other text.** A search of the repository for the titles of the moved bullets finds only `AGENTS.md`. Two knowledge base articles state the principle of the first guard in general words and do not quote it. `devops ai agents` does not write the guards into other repositories.
- **Readers of the file today.** Release v0.2.38 (#1799) deleted `_read_target_conventions` from the review pipeline together with the persona stage. Since then no model prompt of `devops review path`, `branch` or `pr` carries `AGENTS.md` or `.devops/review.md`. Two readers remain. `devops review corpus generate` copies both files into a defect corpus (`commands/review.py`, `generate_corpus`). The pull request checkout in `runner.py` writes both files of the base into the reviewed tree. The change keeps this behaviour: the guards had no reader in the live review before the move, and they have none after it.

## Acceptance Criteria

- [x] `.devops/review.md` holds the six guards word for word. A snapshot pins the full text. The new tests fail on the base tree and pass now.
- [x] Section 5 of `AGENTS.md` no longer lists the guards. It has one pointer bullet, and a test checks that bullet.
- [x] `AGENTS.md` is 1,611 characters shorter, at 37,260 of 40,000. `tests/test_agents_md_claims.py` passes.
- [x] `tests/test_docs_review_loop.py` still finds the `devops review` examples of `AGENTS.md`.
- [x] `uv run devops ci` passes (pre-push hook).
- Pending a person: put #1881 into the milestone of the release branch that takes this pull request. The issue is in the backlog, and `devops pr check-readiness` blocks a pull request into `release/v0.2.39` for an item of the backlog. Agents set no milestone.
- Pending a person: decide whether the guards still need a reader. No model prompt of `devops review` carries them, and the group analysis stage may not originate findings (ADR 0005). If a reader is wanted, a later item passes `nearest_review_conventions` to the analysis stage. If not, a later item deletes the guards.
- Pending a person: decide about GitHub Copilot code review. The GitHub documentation (read on 2026-10-22) says that it reads `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `REVIEW.md` from the head branch of a pull request. It does not list `.devops/review.md`. So it no longer sees the guards on a pull request into `main`. This is the one live reader that the move removes.

## Deliverables

- [x] `.devops/review.md`: the title, the intro and the six guards.
- [x] `src/devops_cli/config/constants.py`: one entry in the prompt class of `CONST_DOCS_INVENTORY`.
- [x] `AGENTS.md`: the pointer bullet "Review Guards" in place of the six guard bullets.
- [x] `tests/test_review_project_conventions.py` and `tests/__snapshots__/test_review_project_conventions.ambr`: the two tests, the snapshot and the two negative controls.
- [x] `docs/agent/tasks/task-1881-review-guards-move-to-devops-review-md.md` and `changelog.d/1881.md`.
