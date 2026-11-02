# Tasks

## 1. The first pass takes more items in a round

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_alternatives.py`, add tests of `select_items` with `limit=5, first_pass_limit=20`: 25 items with no check give the 20 lowest numbers; 8 items with an old check give 5; 3 items with no check and 10 with an old check give the 3 and then the 10 oldest; 2 items with no check whose check failed 1 day ago and 8 items with an old check give 5; `first_pass_limit=None` on 25 items with no check gives `limit`. Add a test of `AlternativesConfig` that the default of `first_pass_limit` is 20 and that 0 is refused. Add a test of the row through `run_due_jobs` with `table=(_alternatives_row(),)` and 25 items with no check, which asserts that the 20 lowest numbers have a comment and a second test of the row with 8 items that have an old check, which asserts 5 comments. Add a test that `plan_alternatives(limit=3)` on 25 items with no check checks 3 items. Change `test_the_row_checks_at_most_the_limit_of_the_setting_and_the_command_uses_it_too`, `test_the_commands_limit_option_has_no_default_of_its_own` and `test_the_limit_setting_defaults_to_five_and_is_at_least_one` so that the items of the limit 2 and limit 1 cases have an old check, and verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [ ] 1.2 In `tests/roadmap/test_roadmap_limit_classes.py`, add the entry `DEFAULT_ROADMAP_ALTERNATIVES_FIRST_PASS_LIMIT` to `LIMITS` with the class `setting` and the reason "items of one round while an item has no check", and verify that `uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` fails on the base
- [ ] 1.3 Add `DEFAULT_ROADMAP_ALTERNATIVES_FIRST_PASS_LIMIT: int = 20` to `src/devops_cli/config/defaults.py` and the field `first_pass_limit` (`ge=1`) to `AlternativesConfig` in `src/devops_cli/config/settings.py`. Add the keyword `first_pass_limit: int | None = None` to `select_items`, so that the cap is `first_pass_limit` when `unchecked` is not empty and the keyword is not `None`, else `limit`. In `plan_alternatives`, pass `config.first_pass_limit` when `limit` is `None`. In `_run_alternatives_adapter` of `src/devops_cli/roadmap/run.py`, call `plan_alternatives(store, repo=repo)`. Update the docstrings of `alternatives.py` and `run.py` that name the limit, and verify that `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 2. The example ConfigMap shows both limits

Reads: `k8s/devops/configmap.example.yaml`, `tests/config/test_k8s_devops_runtime.py`. Changes: `k8s/devops/configmap.example.yaml`.

- [ ] 2.1 Under `roadmap:` in `k8s/devops/configmap.example.yaml`, add the block `alternatives:` with `limit: 5` and `first_pass_limit: 20`, and a comment that says the row takes `first_pass_limit` items while an item has no check and `limit` items after, and verify that `uv run devops ci test tests/config/test_k8s_devops_runtime.py` passes

## 3. The help text and the documents name both limits

Reads: `src/devops_cli/lang/en/help.py`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/CONFIGURATION.md`. Changes: `src/devops_cli/lang/en/help.py`, `docs/roadmap/alternatives.md`, `k8s/README.md`.

- [ ] 3.1 In `src/devops_cli/lang/en/help.py`, change `alternatives_limit` to name `roadmap.alternatives.first_pass_limit` (20) while an item has no check and `roadmap.alternatives.limit` (5) after, and change the sentence "checks at most roadmap.alternatives.limit items" of `run` the same way. In `docs/roadmap/alternatives.md` (section "Which items a run takes") and in point 14 of the Roadmap service in `k8s/README.md`, say the same, and that the row runs about twice a day, so a first pass of 141 items takes about 4 days. Run `uv run devops docs generate --sync-readme` to refresh `README.md`, `docs/CONFIGURATION.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/roadmap.md`, and verify that `uv run devops ci docs` passes

## Criteria

- A test shows 20 items in a round while 25 have no check, and 5 once all have one.: group 1
- The round respects the Service budget and lane order.: group 1
- `uv run devops ci` passes.: pending-person, the required checks of CI gate the merge and the full run is longer than one task command

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
