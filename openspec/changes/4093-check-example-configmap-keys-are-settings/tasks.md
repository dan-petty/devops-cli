# Tasks

## 1. Report a key of the example that no setting declares

Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/k8s/configmap.py`, `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap.py`, `tests/config/test_k8s_devops_runtime.py`. Changes: `tests/k8s/test_k8s_configmap_keys.py` (new), `src/devops_cli/config/setting_keys.py` (new).

- [x] 1.1 Write `test_every_key_of_the_example_is_a_setting`, `test_an_unknown_key_in_a_copy_of_the_example_is_reported` and `test_an_unknown_ladder_step_class_in_a_copy_of_the_example_fails_to_load` in `tests/k8s/test_k8s_configmap_keys.py`. Each renders the example with `render_active_devops_configmap` and fake settings. The tests import `unknown_setting_keys` from `devops_cli.config.setting_keys`, which does not exist on the base
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` fails on the base
- [x] 1.2 Add `src/devops_cli/config/setting_keys.py` with `unknown_setting_keys(config, model=Settings)`. It returns the dotted path of each key of `config` that no field of `model` or of a nested model declares, in the order of the mapping. It goes into a value only when the field is a nested model (alone or in an optional), and reads no key of a plain mapping field
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap_keys.py` passes

## 2. Tell an author to change the live ConfigMap first

Reads: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `.github/pull_request_template.md`. Changes: `tests/invariants/test_configmap_rollout_rule.py` (new), `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Write `test_the_document_holds_the_rule_for_the_live_configmap` in `tests/invariants/test_configmap_rollout_rule.py`. It asserts that `k8s/README.md` and `docs/ROADMAP_WORKFLOW.md` each hold the phrase "removes, renames or tightens" on exactly one line
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` fails on the base
- [x] 2.2 Add one paragraph to "Go-live check" in `k8s/README.md` and one paragraph to `docs/ROADMAP_WORKFLOW.md` (after "Checks of the implement job", or the section that fits the rule best). Each says: a pull request that removes, renames or tightens a setting that `k8s/devops/configmap.example.yaml` or the live ConfigMap names says, in its OpenSpec proposal and in a comment on the pull request, how the live ConfigMap changes first and in which order (apply the ConfigMap with `devops k8s deploy-stack --stack devops`, then let the image roll); and that a test cannot read the live ConfigMap, so `deploy-stack` validates the rendering before it applies it. Add nothing to the pull request template
  - Verification: `$ uv run devops ci test tests/invariants/test_configmap_rollout_rule.py` passes
- [x] 2.3 Check the documents
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `uv run pytest tests/k8s/test_k8s_configmap_keys.py::test_every_key_of_the_example_is_a_setting` fails on the base because the helper that walks the keys does not exist, and passes after the change.
- Group 1: `uv run pytest tests/k8s/test_k8s_configmap_keys.py::test_an_unknown_key_in_a_copy_of_the_example_is_reported` fails on the base for the same reason. The test adds `roadmap.implement.not_a_setting: 1` to a copy and expects the report to name it.
- Group 1: `uv run pytest tests/k8s/test_k8s_configmap_keys.py::test_an_unknown_ladder_step_class_in_a_copy_of_the_example_fails_to_load` adds the key `plan` to the ladder of a copy and expects the error "the ladder names no step class".
- Group 2: `grep -n "removes, renames or tightens" docs/ROADMAP_WORKFLOW.md k8s/README.md` prints one line in each file after the change, and a test in `tests/invariants/` asserts that both files hold the phrase.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
