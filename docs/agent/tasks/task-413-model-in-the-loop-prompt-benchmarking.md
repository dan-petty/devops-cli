# Task: Model-in-the-Loop Prompt Benchmarking (#413)

**Issue**: [#413](https://github.com/dan-petty/devops-cli/issues/413)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description
No tool ran the review prompts through a model and measured the result, so every prompt edit shipped on argument alone. `devops review corpus score` measured recall against injected defects, ground truth the review loop did not produce, but it scored one session at a time, while identical reviews find different defects. Run setups recorded neither the prompts nor the temperature, and with `ai.tasks.verification` unset (the default) they named the base `ai.model` for verification instead of the analysis model that verified.

`VERIFIED` labels come from the verifier under test, so a `VERIFIED` count is a prior, not a label. 633 records are `VERIFIED` today, not the 1066 this item first named. The "122 human-verified records" are not a usable seed: before v0.2.23 the exporter filed every finding without an adjudicator as `human` (ea49d6e). On 2026-10-01 the local data held no human verdicts. This item therefore takes the synthetic corpus's injected defects as ground truth, and every report keeps the synthetic caveat.

An arm is k review sessions of one corpus, run from one checkout with the same prompts. It is scored together, and two arms are compared by their means beside their ranges across runs.

- `src/devops_cli/ai/review/defects.py`: `CorpusScore` gains `candidate_findings`, `invalidated_findings` (status `INVALIDATED`, the verifier's opinion) and `reported_findings`, all set in `score_corpus`. `score_corpus_runs(scores, profiles)` returns a `CorpusRunsScore` with:
  - per-injection `InjectionTally` rows (`found_in`, `reported_in`), keyed by the injection's `id`;
  - `found` and `reported` totals (`pass_at_k`, `pass_hat_k`, `in_none`);
  - one `RunRow` per session: recall, findings, prompt and completion tokens and unparsed persona replies from `profile.json` (0 without one);
  - top-level means named as the run store extracts them (`recall_found`, `recall_reported`, `prompt_tokens`, `completion_tokens`, `candidate_findings`, `invalidated_findings`, `reported_findings`; ratios to 3 decimals, counts to 1, per `RUN_FIGURE_DECIMALS`);
  - `spread` (`[min, max]` per figure, `None` for one run), the full `scores`, the caveat, `runs` and the shared `prompt_digest`.

  It raises `ValidationError` (`devops_cli.exceptions.validation`) when there are no scores, when the profiles do not pair with them, or when the sessions' prompt digests differ, naming each session's digest. Standard library and Pydantic only.
- `src/devops_cli/ai/personas/__init__.py`: `review_prompt_digest(tasks_dir, personas_dir)` applies `run_store.digest` to the relative path and text of every `.md` file under the two directories, defaulting to the package's. `ReviewProfile.prompt_digest` (`ai/review/profile.py`) is set by `ReviewProfiler.build`.
- `src/devops_cli/commands/review.py`: `corpus score` takes a repeatable `--session/-s` and `--runs/-n N` (minimum 1, unset by default). `--runs` takes the latest N sessions whose profile target is the corpus. With neither option it scores the latest one, as before. It exits 1 for `--session` beside `--runs`, for fewer reviews than N (naming how many exist), and for sessions whose digests differ; none of these records a run. The setup is `review_setup(prompt_digest=..., runs=k, personas=...)`, the personas being every one that replied in the scored sessions. The results and `--json` are the `CorpusRunsScore`. The text report has the totals, the mean and range of each figure, one row per run, one row per template (injections, found in any run, found in every run) and one row per injection (`found in x/k`, `reported in y/k`, the finding titles matched in any run), then the caveat. When a gateway group in the setup's pools serves more than one model, it prints `not model-pinned: <group> serves <n> models` (to stderr under `--json`) and still records the run. `_scored_session` and sample validation still score one session with `score_corpus`. The old single-session renderer is removed.
- `src/devops_cli/ai/run_store.py`: `review_setup` resolves verification as `_make_review_clients` does, `ai.for_task("analysis").for_task("verification")`, and records each task's `temperature` and `top_p` under `sampling`. This also changes the setups `review benchmark` and `samples validate --review` record. `unpinned_groups(setup)` names the groups serving more than one model. `_extract_core_metrics` also extracts the three finding counts. `MetricDiff` gains `base_range` and `current_range`, which `compare_runs` fills from each record's `results["spread"]`. `check_regression` is unchanged and still compares means.
- `src/devops_cli/commands/ai_runs.py`: when any metric has a range, the `devops ai runs compare` table adds Base range, Current range and Spread. Spread reads `overlaps`, `apart`, or `—` when either run has no range.
- Docs: help text for `--runs` and the repeatable `--session` (`lang/en/help.py`), regenerated `docs/CLI_REFERENCE.md`, `docs/commands/review.md` and `docs/commands/ai.md`, and a Prompt Benchmarking section in `docs/SELF_IMPROVEMENT.md` that documents the arm, the digest, the setup and the comparison for #475. The changelog entry is `changelog.d/413.md` (#933).

## Acceptance Criteria
- [x] Scoring: `test_an_arm_counts_the_runs_that_found_and_reported_each_injection` (`tests/test_review_defects.py`), 4 injections over 3 sessions, gives tallies `[(3, 2), (2, 0), (1, 0), (0, 0)]`, found `(0.75, 0.25, 1)`, reported `(0.25, 0.0, 3)`, `recall_found` 0.5 with spread `(0.25, 0.75)` and `recall_reported` 0.167 with spread `(0.0, 0.25)`.
- [x] One session reproduces today's totals: `test_an_arm_of_one_run_reproduces_that_sessions_totals` uses the fixture of `test_score_matches_by_line_or_evidence_and_separates_what_verification_kept`. It checks `scores[0] == score`, found pass@1 and pass^1 of 1.0 equal to `score.recall_found`, reported 0.75 and 0.75, counts `(6, 1, 5)` and `spread is None`. The fixture is repeated in a helper, so the existing test is unchanged.
- [x] Refusal in the scoring function: `test_an_arm_refuses_sessions_that_ran_different_prompts` checks that differing digests and an empty arm raise `ValidationError`, the message naming each session's digest.
- [x] CLI: with three corpus sessions (profiles carrying tokens, one unparsed reply and one digest) and one session of another target, `test_corpus_score_scores_the_latest_runs_oldest_first_as_one_arm` checks `--runs 3 --json`: exit 0, `runs == 3`, rows in oldest-first `session_id` order with each profile's tokens and unparsed replies, and `setup["personas"] == ["devsecops", "qa"]`. `test_corpus_score_refuses_more_runs_than_exist_and_says_how_many_do` checks that `--runs 4` exits 1 and says 3 exist. `test_corpus_score_scores_exactly_the_named_sessions` checks that `-s A -s B` scores A and B only, and `test_corpus_score_refuses_session_beside_runs` checks that `-s A --runs 2` exits 1.
- [x] Mixed arms: `test_corpus_score_refuses_runs_of_different_prompts_and_records_nothing` checks that two sessions with different digests under `--runs 2` exit 1, print both digests and record no run.
- [x] Existing tests: the two existing CLI tests changed only their JSON and results paths, to `scores[0]...`. The only other edit to the file's existing code is the `_session` helper, which now passes extra profile fields through. `tests/test_review_sample_validation.py`, which builds `CorpusScore` directly, passes unmodified because the new counts default to 0.
- [x] Prompt digest (`tests/test_review_profile.py`): `test_the_prompt_digest_changes_with_any_review_prompt_and_nothing_else` checks 16 hex characters, the same value on every call, and that a copy of the two directories gives the package's value. One changed character of `tasks/review.md` changes it, one of `personas/devsecops/prompt.md` changes it again, and a `.py` file added to each directory leaves it unchanged. `test_a_profile_records_the_digest_of_the_prompts_it_ran_with` checks `ReviewProfiler().build(...)`.
- [x] Setup (`tests/test_run_store.py`): `test_a_review_setup_names_the_model_and_sampling_that_verified` patches `gateway_pool` and uses settings where only `ai.tasks.analysis` names a gateway group (`devops-coder`, temperature 0.3, `top_p` 0.8) and the base `ai.model` names another. It checks that verification equals analysis, that `pools` holds only `devops-coder`, and that both tasks record 0.3 and 0.8. `test_unpinned_groups_are_those_serving_more_than_one_model` covers the pinning predicate.
- [x] Comparison (`tests/test_run_comparison.py`): `test_comparing_arms_reads_their_difference_against_each_ranges` gives ranges `((0.25, 0.75), (0.5, 1.0))` read `overlaps`, `(0.8, 1.0)` read `apart`, and, for a one-run score (`spread: null`) and a record without `spread`, a `None` current range read `—`. `test_runs_without_a_spread_compare_without_range_columns` checks that no range columns appear when neither run has a range. `test_comparing_arms_compares_their_finding_counts_beside_their_ranges` checks that `compare_runs` reads each arm's `candidate_findings`, `invalidated_findings` and `reported_findings` (base and current means, base and current ranges), and that the table marks those rows `overlaps`, `—` and `apart`. With the three counts removed from `_extract_core_metrics`, it fails with a `KeyError`. The file's existing tests pass unmodified: its diff adds two imports and the new tests after them, and `test_cli_runs_compare_and_check` still drives `devops ai runs compare A B` through the full app.
- [x] Pinning: `test_corpus_score_warns_when_a_gateway_group_serves_several_models` patches `review_setup` with a `devops-review` pool serving `qwen3-coder:30b` and `gpt-oss:20b`. The text report contains `not model-pinned: devops-review serves 2 models` and the run is recorded.
- [x] The new tests touch no network, cluster or model. Sessions and corpora are temporary files, `gateway_pool` and `review_setup` are patched where a pool is needed, and the corpus-score CLI tests stub the commit lookup. The new CLI tests drive the `corpus` and `runs` groups' own Typer apps, which parse the commands as `devops` does without building every other command. Existing tests keep the full app. Each new test runs in under 0.5 s (see Measurements).
- [x] `ruff check`, `ruff format` and `mypy --strict` are clean on every touched module. `devops scan complexity` reports nothing new: its findings in `run_store.py` (`get_run`) and `commands/review.py` (`path`, `list_findings`) are the same at HEAD. `uv run devops docs check` passes after `devops docs generate --sync-readme`.
- Pending a person: `uv run devops ci` on the delivering tree, which the orchestrating session runs.
- Pending a person: the live-model check, never part of `devops ci`. Copy the main checkout's `config.yaml` outside both checkouts, and in the copy set `ai.tasks.analysis.model` and `ai.tasks.verification.model` to `devops-coder`, both on the gateway provider. Export `DEVOPS_CLI_CONFIG` to the copy in both worktrees. Generate a corpus with `--seed 1` from `src/devops_cli/core src/devops_cli/security src/devops_cli/crypto`. Run `review benchmark "$CORPUS/files" --all --runs 3` then `corpus score "$CORPUS" --runs 3` twice for arm A (A/A), and set the first as the baseline. Then edit one prompt in a second worktree and run the same for arm B. `devops ai runs compare <A2>` should show identical setups, `devops ai runs compare <B>` should list `prompt_digest` as the only setup difference, and no `not model-pinned` line should appear. The PR description records the A/A ranges as the noise floor. If A2's ranges read `apart` from A's, file the follow-up to run benchmarks under `catalog_learning_disabled()`.
- Not checked when merged: the PR's own remote checks.

## Measurements
New-test durations from `uv run pytest -p no:cacheprovider tests/test_review_defects.py tests/test_review_profile.py tests/test_run_store.py tests/test_run_comparison.py --durations=0` (xdist `-n logical`, 82 passed). Each figure is setup, call and teardown summed. The machine was shared with other agents' gates, at a one-minute load of 15 to 22 on 16 cores.

| Test | Time |
| :--- | ---: |
| `test_corpus_score_scores_the_latest_runs_oldest_first_as_one_arm` | 0.47 s |
| `test_corpus_score_warns_when_a_gateway_group_serves_several_models` | 0.42 s |
| `test_corpus_score_refuses_more_runs_than_exist_and_says_how_many_do` | 0.40 s |
| `test_comparing_arms_reads_their_difference_against_each_ranges[apart]` | 0.34 s |
| `test_the_prompt_digest_changes_with_any_review_prompt_and_nothing_else` | 0.29 s |
| `test_comparing_arms_compares_their_finding_counts_beside_their_ranges` | 0.24 s* |
| `test_corpus_score_scores_exactly_the_named_sessions` | 0.24 s |
| `test_comparing_arms_reads_their_difference_against_each_ranges[overlapping]` | 0.22 s |
| `test_runs_without_a_spread_compare_without_range_columns` | 0.22 s |
| `test_corpus_score_refuses_runs_of_different_prompts_and_records_nothing` | 0.19 s |
| `test_corpus_score_refuses_session_beside_runs` | 0.18 s |
| `test_an_arm_refuses_sessions_that_ran_different_prompts` | 0.15 s |
| `test_comparing_arms_reads_their_difference_against_each_ranges[no-spread]` | 0.13 s |
| `test_an_arm_counts_the_runs_that_found_and_reported_each_injection` | 0.13 s |
| `test_comparing_arms_reads_their_difference_against_each_ranges[one-run-score]` | 0.10 s |
| `test_a_profile_records_the_digest_of_the_prompts_it_ran_with` | 0.10 s |
| `test_a_review_setup_names_the_model_and_sampling_that_verified` | 0.06 s |
| `test_an_arm_of_one_run_reproduces_that_sessions_totals` | 0.03 s |
| `test_unpinned_groups_are_those_serving_more_than_one_model` | 0.01 s |

\* Added after the table was measured. The four files then gave 83 passed. Under a load of 18 to 30, that command inflated every figure three to seven times, so this one comes from three runs of the comparison tests in one process (`-n 0`, load 11 to 17). The figure is the fastest of 0.24, 0.26 and 0.28 s, its parametrized neighbours taking 0.12 to 0.17 s at their fastest. The roughly 12 s setup paid by whichever test runs first in a process is session warm-up, and `test_baseline_management` pays it the same way.

Driven through the full `devops` app, each `corpus score` invocation cost about 0.14 s more in Typer command building, and under that load the slowest CLI test reached 1.15 s. That is why the new CLI tests use the group apps.
