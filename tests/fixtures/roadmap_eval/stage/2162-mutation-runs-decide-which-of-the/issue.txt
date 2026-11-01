### What happened

The coverage audit of 2026-10-24 (per-test contexts of a full run at f4d7066b) found 86 test files that cover no line of `src/` that another file does not also cover. 18 of them test the review and the scanners. For several, one other file covers 84-100% of the same lines. Line coverage alone cannot show that a file is redundant, because a file can cover a line and still assert something that no other file asserts. Mutation testing can show it: a file that kills no mutant that the rest of the suite leaves alive adds no check.

| File | Tests | Lines covered beyond the import baseline |
| :--- | ---: | :--- |
| `tests/ai/review/test_cited_code.py` | 2 | 1716, 99% in `tests/test_review_group_analysis.py` |
| `tests/commands/test_review.py` | 2 | 802, 100% in `tests/test_review_adjudication.py` |
| `tests/commands/test_review_removed_options.py` | 1 | 8 |
| `tests/test_custom_personas.py` | 3 | 21 |
| `tests/test_review_advisory_backing.py` | 1 | 280 |
| `tests/test_review_deduplication.py` | 4 | 377, 92% in `tests/test_review_pipeline.py` |
| `tests/test_review_defects_comments.py` | 1 | 171 |
| `tests/test_review_defenses_and_verification.py` | 7 | 631, 84% in `tests/test_review_tool_runs.py` |
| `tests/test_review_history.py` | 6 | 1815, 98% in `tests/test_review_group_analysis.py` |
| `tests/test_review_location_paths.py` | 5 | 153 |
| `tests/test_review_loop_hardening.py` | 5 | 162 |
| `tests/test_review_regression_harness.py` | 2 | 603, 94% in `tests/test_review_finding_losses.py` |
| `tests/test_review_taxonomy_and_severity.py` | 7 | 163 |
| `tests/test_review_verification.py` | 8 | 1300, 85% in `tests/test_review_runner.py` |
| `tests/test_structural_positional_oracles.py` | 3 | 127 |
| `tests/test_security_kubelinter.py` | 8 | 538, 88% in `tests/test_security_sarif.py` |
| `tests/test_security_tflint.py` | 3 | 896, 92% in `tests/test_security_kubeconform.py` |
| `tests/security/test_sarif_fuzzing.py` | 5 | 240 |

### What should happen

Mutation runs decide, file by file, whether a file adds a check. A file that kills no mutant of its own is deleted, or its one distinct case moves into the file that covers the same lines. A file that kills a mutant of its own stays, and the pull request names the mutant.

### Evidence

- `.data/agent/scratch/audit-coverage/unique-lines-nobaseline.json` and `subsumption.json` of the 2026-10-24 coverage audit (contexts of a full `pytest --cov-context=test` run at f4d7066b).
- Every file in the table exists at b170358e.
- `uv run devops ci mutate --help`: mutmut over the given `src/` files; the first run copies the tree and runs the suite once.

### Key questions

- *How is a mutant "of its own" found?* (proposed) For each file, mutate the functions whose lines the file covers, once with the whole suite and once with the file left out (mutmut's `pytest_add_cli_args_test_selection`, `--ignore=<file>`). A mutant that survives only when the file is left out is the file's own.

### Acceptance criteria

- [ ] The pull request gives, for each file in the table, the mutants it killed with the whole suite and the mutants that survive without it.
- [ ] Each file with no mutant of its own is deleted, or its distinct case moves into the file that covers its lines. The line coverage and `fail_under` stay as they are or rise.
- [ ] No contract suite, invariant test or test of a security guard is deleted by this item.
- [ ] `uv run devops ci` passes, and the `Tests & Coverage` job takes no longer than before.

Related: #1328 owns the move of the `ai/review` tests onto fakes; a file this item deletes leaves that work. The 86 files also hold invariant and helper tests, which other issues of the same audit own.


Source: https://github.com/dan-petty/devops-cli/issues/1328

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The test suite has 18 review and scanner test files that cover no unique line of source code beyond what other files already cover. Line coverage alone cannot prove a file is redundant because a file can cover a line and still assert a unique behavior. Mutation testing determines whether each file kills a mutant that the rest of the suite leaves alive. A file that kills no such mutant adds no check and is deleted or merged into the file that covers the same lines.

### Acceptance criteria
- Criterion 1: The pull request records, for each of the 18 files, the mutants it killed with the whole suite and the mutants that survive without it.
  Verification: Read the pull request description or a committed report file. Confirm it lists each file name, the mutant IDs it killed, and the mutant IDs that survive when the file is excluded.
- Criterion 2: Each file with no mutant of its own is deleted, or its distinct test case is moved into the file that covers the same lines.
  Verification: Run `git diff --name-status` on the pull request. Confirm every deleted or modified test file matches a file in the 18-file table. Run `uv run pytest --cov=devops_cli --cov-report=term` and confirm the line coverage percentage and `fail_under` threshold are unchanged or higher.
- Criterion 3: No contract suite, invariant test, or test of a security guard is deleted by this item.
  Verification: Run `git diff --name-only --diff-filter=D` on the pull request. Confirm no file matching `test_architectural_invariants`, `test_contract`, or a security-guard test name appears in the deleted set.
- Criterion 4: `uv run devops ci` passes and the `Tests & Coverage` job takes no longer than before the change.
  Verification: Run `uv run devops ci` locally and confirm exit code 0. Compare the `Tests & Coverage` job duration in the pull request check runs with the duration on the base branch.

### Key questions
- **How is a mutant "of its own" found?**: For each file, mutate the functions whose lines the file covers. Run the suite once with all tests and once with the file excluded via `--ignore=`. A mutant that survives only when the file is excluded is the file's own mutant. The tool is `uv run devops ci mutate`, which runs mutmut over the given `src/` files. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "380c8709cf87c2ecfd8f9adeb5369d6d43e172ec67754c9578dbee759f6eca8a", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "c24c33784a5258afd2254586298afe632bbe1019844f47d74d3d2c0b766260fe", "stage.branch": "test/2162-mutation-runs-decide-which-of-the", "stage.file_cap": null, "stage.groups": "[[\"Run mutation testing and write the report\", 4232], [\"Delete or merge files with no unique mutant\", 4283], [\"Verify CI passes and mark tasks complete\", 4062]]", "stage.needs_split": null, "stage.pr": "2979", "stage.ready": "2979", "stage.sha": "af44f35beba21404c95597e22a0e6ead82a63db6"} -->
