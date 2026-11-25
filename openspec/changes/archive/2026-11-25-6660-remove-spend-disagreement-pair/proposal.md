# Proposal: #6660

## Why
`src/devops_cli/roadmap/project_review/catalog.yaml` defines the `spend` disagreement pair comparing `prometheus.cli_spend` (`sum(increase(devops_cli_ai_spend_usd_total[{range}]))`) with `prometheus.gateway_spend` (`sum(increase(litellm_spend_metric_total[{range}]))`). The gateway spend counter includes every gateway caller, while the stage Job, runner Jobs, and CLI send the gateway master key (`api_key_alias=None`), so no label selects the same call set as `devops_cli_ai_spend_usd_total`. Comparing them produces false disagreements across review windows.

## What Changes
- Remove the `spend` disagreement pair from `src/devops_cli/roadmap/project_review/catalog.yaml`.
- Keep `prometheus.cli_spend` and `prometheus.gateway_spend` as separate facts in the catalog.
- Update `openspec/specs/roadmap-project-review/spec.md` and project review tests to verify that `spend` is absent from `catalog.disagreements` while both spend facts remain active.

## Capabilities
- Modified: `roadmap-project-review`

## Impact
- `src/devops_cli/roadmap/project_review/catalog.yaml`
- `openspec/specs/roadmap-project-review/spec.md`
- `tests/roadmap/project_review/test_review_catalog.py`
- `tests/commands/test_roadmap_review.py`

Fits in one pull request.

## Feasibility
Confirmed on `origin/main`:
- `src/devops_cli/roadmap/project_review/catalog.yaml:903-938` defines `prometheus.gateway_spend`, `prometheus.cli_spend`, and disagreement pair `id: spend`.
- `k8s/devops/cronjob-stage.yaml:110` and `k8s/devops/cronjob-runner.yaml:167` pass the shared Secret key instead of per-client virtual keys, so `litellm_spend_metric_total` has no client-selecting alias label (`#6165` and `#6002` track the remaining gateway streamed-call and deployment-pricing gaps).

## Existing Tool Considered
LiteLLM (`BerriAI/litellm`) is already in use for the gateway (`k8s/llm/gateway/config.yaml`). Virtual keys with `api_key_alias` exist only for the roadmap Service deployment (`src/devops_cli/commands/k8s/roadmap_key_bootstrap.py`), not for Jobs or CLI callers, and streamed/deployment pricing gaps remain tracked in `#6165` and `#6002`. Removing the mismatched pair avoids building per-client virtual-key distribution here and stops misleading disagreements immediately.
