# Proposal

## Why

Issue #4093 reports that on 2026-11-07 the roadmap Service crashed after a release, because the live ConfigMap `devops-cli-config` still held two ladder keys that PR #4074 had removed. The example `k8s/devops/configmap.example.yaml` was correct, and a test of it would have failed. The live ConfigMap is not in git, and no document tells an author to change it first.

A second gap is still open. Most models of `Settings` set `extra="ignore"`, so a key that a change removes from a model, and that stays in the example, loads with no error. No test reports it.

## What Changes

- Add `unknown_setting_keys(config, model=Settings)` in the new module `src/devops_cli/config/setting_keys.py`. It walks the keys of a settings mapping against `model_fields` of the models, goes into each nested model, and returns the dotted path of each key that no model declares. It reads no file and starts no process.
- Add `tests/k8s/test_k8s_configmap_keys.py` with three tests. `test_every_key_of_the_example_is_a_setting` renders the example with `render_active_devops_configmap` and fake settings, loads it with `Settings.model_validate`, and expects no unknown key. `test_an_unknown_key_in_a_copy_of_the_example_is_reported` adds `roadmap.implement.not_a_setting: 1`, and a second case adds a top-level key, and expects the report to name each one. `test_an_unknown_ladder_step_class_in_a_copy_of_the_example_fails_to_load` adds the ladder key `plan` and expects the error "the ladder names no step class".
- Add the rule to `k8s/README.md` (the paragraph "Go-live check") and to `docs/ROADMAP_WORKFLOW.md`: a pull request that removes, renames or tightens a setting that the example ConfigMap names says, in its OpenSpec proposal and in a comment on the pull request, how the live ConfigMap changes first and in which order: apply the ConfigMap, then let the image roll. The pull request body stays as the template sets it, because it becomes the squash message, so the change adds no line to the template.
- Add `tests/invariants/test_configmap_rollout_rule.py`, which asserts that each of the two documents holds the phrase "removes, renames or tightens" on one line.
- State here that a test of the repository cannot read the live ConfigMap. The check at deploy time covers the cluster: `render_devops_configmap_content` in `src/devops_cli/k8s/configmap.py` calls `Settings.model_validate` on the rendering, and `devops k8s deploy-stack --stack devops` refuses to apply a rendering that does not load.
- This change removes, renames and tightens no setting, so it needs no rollout step for the live ConfigMap.
- The change adds a module that no consumer observes (a helper that only tests call) and edits documents and tests, so it has no spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Source: `src/devops_cli/config/setting_keys.py` (new)
- Tests: `tests/k8s/test_k8s_configmap_keys.py` (new), `tests/invariants/test_configmap_rollout_rule.py` (new)
- Documents: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`

## Feasibility

- Command output of 2026-11-08, from a probe script that walks `model_fields` of `Settings` (nested models only) over the example `k8s/devops/configmap.example.yaml`: `keys walked: 52 unknown: []`. So the example holds 0 unknown keys now, and the claim of the issue ("none is unknown") is confirmed by a tool.
- The same probe, after it added `roadmap.implement.not_a_setting: 1` and a top-level `bogus: 1` to a copy, printed `['roadmap.implement.not_a_setting', 'bogus']`. `Settings.model_validate` loaded the same copy with no error, because `extra="ignore"` holds for those models. So the gap is real, and a walk over `model_fields` closes it with no new dependency.
- `grep -n "extra=" src/devops_cli/config/settings.py` shows 13 models with `extra="ignore"` and `validate_assignment=True`, one with `extra="ignore"` alone and 3 with `extra="forbid"`. So most models ignore an unknown key.
- `render_active_devops_configmap(k8s_dir, settings)` in `src/devops_cli/k8s/configmap.py` renders and validates the example with fake settings, and `tests/k8s/test_k8s_configmap.py` uses the same pattern (`Settings(service=ServiceConfig(repos, github_app))`). No test of the repository reads the live ConfigMap, and none can: the cluster holds it and git does not.
- `src/devops_cli/config/settings.py` `_check_ladder` raises "the ladder names no step class" for a ladder key that is no step class, so the third test passes on the load alone.
- The phrase "removes, renames or tightens" is in no file of the tree now (`git grep -n "removes, renames or tightens"` prints nothing).
- Open and merged pull requests: #4074 removed the ladder keys (merged). #1231 (a generated ConfigMap) is closed. No open pull request does this work. Open #4121 (issue #4094) edits only the example values, so it does not conflict.
- `devops ci fail-to-pass` overlays the `tests/` tree of the head on the base tree, so a helper in `tests/support/` would also exist on the base. The helper is therefore a module of `src/`, and the new tests fail on the base by a missing module.

## Existing Tool Considered

Pydantic reports a key that no field declares when a model sets `extra="forbid"`. The ConfigMap loader could validate with strict copies of the models, but that changes a public behavior: `extra="ignore"` lets old config files load, and the 3 models that forbid keys already show the cost of that (#2201). `kubeconform` and `kubectl diff` check the shape of a manifest, not the meaning of the settings inside the string `devops-cli.yaml`, so they do not fit. The change builds one small walk over `model_fields`. Cost: about 30,000 tokens to build, low to keep (a new setting needs no edit, because the walk follows `model_fields`), and about 1 hour. A repeat of the crash of 2026-11-07 stops the roadmap Service until a person applies the ConfigMap. The change deletes no internal code.

## Dependencies

None.
