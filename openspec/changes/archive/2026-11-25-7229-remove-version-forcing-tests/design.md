# Design

## Decisions

1. **A fixed value goes, a generic rule stays.** A test goes when it holds a value, a name list or a count of a real file, a default or a constant. A test stays when it applies one rule to each member of a set and holds no literal of a real file, because it does not fail on an update. Kept for this reason: `test_every_remote_action_is_pinned_to_a_commit_sha`, `test_no_run_block_interpolates_an_actions_expression`, `test_every_checkout_states_its_credentials_and_only_a_pushing_job_keeps_them`, `test_every_job_has_a_limit_and_each_step_limit_is_under_it`, the attestation contract and its mutation test, the two tests of the pre-push time sum, `test_image_path_filter_covers_dockerfile_sources`, `test_service_dockerfile_base_images_pinned_by_digest` (now the digest form only), `tests/ci/test_release_download_retries.py`, the lockfile test of `test_devcontainer_config.py`, the key binding test of `test_gh_dash_config.py` and `test_agents_md_stays_within_character_budget`.
2. **The gray tests go.** A test that holds a value of a real file and also guards a safety property goes too (owner decision of 2026-11-25). The property stays in the file that holds it.
3. **A test of source code keeps its behavior and loses the literal.** It compares with the constant or the setting that the code reads, for example `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` in `tests/commands/test_pr_dry_run.py`.
4. **The snapshot of the implement step holds its own rules.** The test writes a short `AGENTS.md` into its checkout, so the snapshot does not hold the rendered template of `devops ai agents`.
5. **The style request test compares with the prompt file.** It loads `style_ste100.md` with `load_task_prompt` and needs no snapshot.
6. **The location of the suppression ceilings is computed.** `tests/invariants/test_architectural_invariants.py` held the line number 133 of its own table as a literal, and the removal of a constant above the table failed `test_the_breach_message_names_the_ceiling_definition_and_the_fix`. The file now finds the line.
7. **The live test of the planner Job stays.** `test_the_run_job_holds_the_three_controls` runs in a real cluster (`pytest -m k8s`) and reads no value of a manifest.

## Rejected alternatives

- **Change the literal at each update**: rejected, because 19 of 109 dependency update commits since 2026-11-01 had to change a file under `src/` or `tests/`.
- **Remove each of the 245 tests of `config_reads.toml`**: rejected, because the tests that stay take a committed file as input and assert no value of it, such as the 8 tests of `tests/commands/test_environment_root_commands.py`, which compare the tree with a copy.
- **Remove the gate checks of `tests/gate/k8s_checks/` in this change**: rejected, because they are rows of `devops ci` and not tests, and 22 of the 25 modules are not read yet (#7231).
- **Remove the sentence tests of documents and prompts**, such as the rule tests of `tests/invariants/test_agents_md.py`: rejected for this change, because the issue names versions and settings, and these tests hold sentences. The owner decides this class.
