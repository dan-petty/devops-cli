# Proposal

## Why

Issue #3229: PR #3223 (#3206) raised the default of `roadmap.stage.step_tokens` from 40,000 to 64,000, which is half of the implement window. `k8s/devops/configmap.example.yaml` still sets `step_tokens: 40000`, so a deploy from the example keeps the old budget and the new default does not reach the Service. Three tests also pin tuned values of the example (the stage filter, limit and step tokens; the models, the window and the telemetry endpoint), so each tuning of the example is a test change.

## What Changes

- `k8s/devops/configmap.example.yaml` sets `roadmap.stage.step_tokens` to 64000, the value of `DEFAULT_ROADMAP_STAGE_STEP_TOKENS`.
- The test `test_the_repository_template_sets_the_stage_job_of_the_service` is removed. It pinned the filter, the limit and the step tokens of the example, and no requirement states them.
- `test_config_targets_the_in_cluster_gateway_and_holds_no_credential` keeps three checks: the example validates as settings, the provider is `gateway` with an address in the cluster, and no credential is set. It no longer pins the models, the retry count, the window or the telemetry endpoint.
- `test_configmap_validates_as_settings_with_repos_and_the_github_app` no longer pins the telemetry endpoint and the analysis window. It keeps the checks that the example names repositories, the bot login and enables telemetry.
- `test_the_repository_template_renders_one_model_retry_for_the_cluster` stays: the requirement "A model call in the cluster is sent at most two times" in `roadmap-service-deployment` states `ai.max_retries` 1, and that test is its scenario.
- The change alters no behavior that a consumer observes, because no spec states the example values that change. It has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/devops/configmap.example.yaml`.
- Tests: `tests/k8s/test_k8s_configmap.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

## Feasibility

Checked on 2026-11-02 at `origin/main` (`bc0434ee`).

- `git grep -n "step_tokens" -- k8s/devops/configmap.example.yaml` finds `step_tokens: 40000` on line 64, and `git grep -n "DEFAULT_ROADMAP_STAGE_STEP_TOKENS =" -- src/devops_cli/config/defaults.py` finds 64000.
- `git grep -n -e "step_tokens" -e "40000" -- tests/k8s/test_k8s_configmap.py` finds the pin at line 246 and the check against `Settings` at line 248.
- No spec states the values that change: `git grep -n -e "configmap.example" -- openspec/specs` finds only the requirement "A model call in the cluster is sent at most two times" (`roadmap-service-deployment`) and a scenario of `llm-valkey`. `git grep -n -e "65536" -e "otel-collector-opentelemetry" -e "deepseek-v4" -- openspec/specs` finds the window in `roadmap-alternatives` (an investigation scenario, not the example) and the gateway groups in `ai-gateway-routing` (the gateway, not the example).
- After the change, `uv run devops ci test tests/k8s/test_k8s_configmap.py tests/config/test_k8s_devops_runtime.py tests/server/routes/test_k8s_roadmap_service.py tests/roadmap/test_roadmap_limit_classes.py` passes (151 tests with the gateway and Valkey tests).

## Existing Tool Considered

No open tool covers the edit of one value of an example and three tests. The cost is about 20,000 tokens and 30 minutes to build, and nothing to keep. Keeping the pins costs a test change for each tuning of the example.
