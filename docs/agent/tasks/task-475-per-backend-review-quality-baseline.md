# Task: Per-Model Review Quality Baseline for the devops-review Pool (#475)

**Issue**: [#475](https://github.com/dan-petty/devops-cli/issues/475)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/review

## Description
`devops-review` serves every review call, persona review and verification alike, from two models: `qwen3-coder:30b` on ollama-48gib (weight 9) and ollama-64gib (6), and `gpt-oss:20b` on ollama-16gib (8) and ollama-24gib (1). The gateway's weights track throughput alone, and nothing measured review quality per model: no finding names the model that produced it, and `served_by` names a tier, not a model. #476 found that faster weights reported more findings, including top-severity false positives that passed verification, and left the question to this item.

Pinning one model per arm measures each model end to end, generating and verifying, with no schema change. Three things prevented it, and this change removes them. The measurement itself calls live models, so a person runs it; the gate never does (#413).

- `k8s/llm/gateway/configmap.yaml`: the groups `qwen3-coder:30b` and `gpt-oss:20b` copy their model's `devops-review` deployments exactly (model, `api_base` and weight, in order), with no `model_info` and no fallback. With `enable_pre_call_checks` on, a `max_input_tokens` the pool lacks would route differently from it. `devops-coder` and `devops-reasoning` also reach `qwen3-coder:30b` alone, but on ollama-48gib only, and their fallbacks end at `devops-chat`, whose `qwen3.8:27b` shares ollama-48gib, so `served_by` could not show the switch. `gpt-oss:20b` had no group since the `ollama/*` route left the configmap (#734). They follow the per-model groups `gemma4:31b` and `qwen3.8:27b`, and they stay for #480 and later candidate models. `devops-review` and its weights are unchanged. `get_gateway_routing_entries` (`src/devops_cli/k8s/gpu_matrix.py`), which mirrors the ConfigMap's model list, gains the same four entries, and `k8s/README.md` names the groups in its gateway section.
- `src/devops_cli/config/options.py` and `config/env.py`: `DEVOPS_CLI_AI_TASK_VERIFICATION_PROVIDER`, `_MODEL`, `_REASONING_EFFORT` and `_OLLAMA_URLS` set `ai.tasks.verification.*` through `OPTION_TO_ENV_VAR`. They mirror the analysis task's option names, map entries and `EnvVarSpec` entries, so provider, model and Ollama URLs are listed in `docs/ENV_VARS.md`, as analysis's are. Before, an arm that set only `DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL` still verified on the whole pool, because reviews layer a configured `ai.tasks.verification.model: devops-review` on the analysis task.
- `src/devops_cli/commands/review.py`: `devops review benchmark --no-static-scan` passes `no_static_scan` to every `path` run and records `static_scan` in the run's setup, beside `pre_analysis`. Scanner findings carry no producer and the run's model verifies them, so a scanner hit on an injected defect scored as found in every arm.
- Each arm keeps its own sessions and pre-analysis metadata through the existing `DEVOPS_CLI_DATA_REVIEWS_DIR` and `DEVOPS_CLI_DATA_ANALYSIS_DIR`, with `DEVOPS_CLI_DATA_DIR` unset (it takes precedence over the reviews directory). That keeps arm sessions out of `devops review stats`, `export-feedback` and the #434 baseline (#607), and limits each arm's `corpus score --runs` to its own sessions. A review's pre-analysis makes no model call: `_execute_pre_analysis_batch` (`src/devops_cli/ai/review/pipeline.py`) passes `ai_client=None` to `analyze_single_file`, so its metadata is AST-only and the same for every model. It does reuse matching entries from the latest file in `data.analysis_dir`, and `devops ai analyze` enhances metadata with a model by default, so a shared directory could carry one model's pseudocode into both arms' review and verification prompts. Each arm's directory starts empty, so both arms review with the same deterministic metadata. No code change was needed for this.
- Docs: `docs/SELF_IMPROVEMENT.md` (Prompt Benchmarking) says how to compare models rather than prompts. `docs/CLI_REFERENCE.md`, `docs/commands/review.md`, `docs/commands/ai.md` and `docs/ENV_VARS.md` are regenerated. The changelog entry is `changelog.d/475.md`.

Decisions, as the issue settled them:
- Measure per model, not per tier. Each arm spreads its calls over its model's tiers with the pool's weights, so `gpt-oss:20b` is measured mostly on ollama-16gib, as the pool serves it. `profile.json` records every call's tier.
- Ground truth is the synthetic corpus's injected defects, never the verifier being measured (#413). No human verdicts exist, so the decision rests on recall alone. Reported findings that match no injection are counted by severity as "unlabelled", not called false positives, because the corpus source can hold real defects.
- Corpus, personas (`--all`), k and the configured temperature are the same in both arms; scanners are off.
- Decision rule, fixed before the runs: a quality factor is warranted when one model's reported pass@k is below the other's by more than the run-to-run spread #413 reports for either arm, that is, by more than the wider of the two arms' `recall_reported` ranges. Otherwise the weights stay throughput-only. Unlabelled findings do not enter the rule; the results give them by severity beside the outcome, since #476's concern was extra top-severity findings.
- This item changes no `devops-review` weight. If a factor is warranted, a follow-up issue carries the figures and either adds a quality multiplier to `recommend_weights` (`src/devops_cli/ai/gateway_tune.py`) or takes `gpt-oss:20b` out of the pool, and re-runs #476's A/B. If `gpt-oss:20b` comes out worse, a follow-up first compares ollama-16gib (q4_0 KV cache) with ollama-24gib (q8_0).
- Out of scope: `gemma4:31b`, `qwen3.8:27b` and `deepseek-r1:70b`, whose groups already exist, so the same commands can measure them later. Split off: #871 (findings record their producer, a scanner rule or the serving model) and #872 (a dry-run review writes no session directory or findings).

## Measurement (person-run)
From this branch before merge, with `DEVOPS_CLI_DATA_DIR` unset. Sources, seed and k are #413's. Directory names carry no colons, because the workspace may sit on a Windows share.

```sh
kubectl apply -f k8s/llm/gateway/configmap.yaml
kubectl -n llm rollout restart deployment/llm-gateway && kubectl -n llm rollout status deployment/llm-gateway
uv run devops ai gateway routes
kubectl get pods -n llm                                   # note restart counts
uv run devops review corpus generate src/devops_cli/core src/devops_cli/security src/devops_cli/crypto --seed 1 --out .data/475/corpus
for arm in qwen3-coder=qwen3-coder:30b gpt-oss=gpt-oss:20b; do
  name=${arm%%=*} model=${arm#*=}
  # Own sessions and pre-analysis cache per arm, kept out of review stats and the #434 baseline.
  export DEVOPS_CLI_DATA_REVIEWS_DIR="$PWD/.data/475/$name/reviews" DEVOPS_CLI_DATA_ANALYSIS_DIR="$PWD/.data/475/$name/analysis"
  export DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=$model DEVOPS_CLI_AI_TASK_VERIFICATION_MODEL=$model
  uv run devops review benchmark .data/475/corpus/files --all --no-static-scan -n 3
  uv run devops review corpus score .data/475/corpus --runs 3
done
kubectl get pods -n llm                                   # restart counts unchanged
```

Review pre-analysis is AST-only and makes no model call, so an arm's analysis directory does not pin a model. It keeps metadata that `devops ai analyze` enhanced with some other model out of both arms.

The learned false-positive catalog is not per arm: with `DEVOPS_CLI_DATA_DIR` unset it lives under the main worktree's data directory, and verification adds entries to it from deterministic invalidations. The second arm therefore verifies with entries the first arm's runs taught (see the A/A note under Prompt Benchmarking in `docs/SELF_IMPROVEMENT.md`).

## Acceptance Criteria
- [x] Per-model groups (`tests/test_k8s_llm_gateway.py`): `test_a_review_model_has_a_group_of_its_review_deployments_alone`, parametrized over `qwen3-coder:30b` and `gpt-oss:20b`, checks that the model's `devops-review` entries exist, that the group's (model, `api_base`, weight) triples equal them in order, that each group entry holds only `model_name` and `litellm_params` with only `api_base`, `model` and `weight`, and that the group is neither source nor target in `fallbacks` or `context_window_fallbacks`. Adding `model_info.max_input_tokens` to one `gpt-oss:20b` entry, or a `qwen3-coder:30b` fallback, failed the matching case; both cases passed again on the restored file.
- [x] `test_gateway_configmap_virtual_models` lists both groups after `devops-review`. `test_gateway_routing_entries_generation` (`tests/test_k8s_gpu_matrix.py`) checks 25 entries, both groups among the model names, and that `get_gateway_routing_entries()` still equals the ConfigMap's model list.
- [x] Verification overrides (`tests/test_config_env_overrides.py`): `test_the_environment_pins_review_analysis_and_verification_to_one_model` writes a config whose analysis task is `gateway`/`devops-review` and whose `ai.tasks.verification.model` is `devops-review`, sets `DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL` and `DEVOPS_CLI_AI_TASK_VERIFICATION_MODEL` to `gpt-oss:20b` and stubs `gateway_pool`. It checks `load_settings().ai.tasks.verification.model == "gpt-oss:20b"`, a verification client from `_make_review_clients` with provider `gateway` and model `gpt-oss:20b`, `review_setup()["models"] == {"analysis": "gateway/gpt-oss:20b", "verification": "gateway/gpt-oss:20b"}` and `pools == {"gpt-oss:20b": <stub>}`. Without the new map entries it failed with verification still `devops-review`.
- [x] Benchmark (`tests/test_run_store.py`): `test_a_review_benchmark_can_review_without_static_scanners`, modeled on `test_a_review_benchmark_is_kept_with_its_setup_and_corpus`, runs `review benchmark <corpus> -n 2` with `review path` patched. With `--no-static-scan` both calls get `no_static_scan=True` and the kept run's setup has `static_scan: false`; without it both get `False` and the setup has `static_scan: true`.
- [x] Every assertion is a structural tuple. The tests touch no network, cluster or model: the ConfigMap is read from disk, `gateway_pool` and `review path` are patched, and the benchmark test drives the `review` group's Typer app. The five new cases add about 0.3 s together (see Measurements).
- [x] `ruff check`, `ruff format --check` and `mypy --strict` are clean on every touched module. `uv run devops docs check` passes after `uv run devops docs generate --sync-readme`.
- Roadmap: not edited in this change. Item PRs never edit `docs/ROADMAP.md`; `devops roadmap render` regenerates it from GitHub at the cut, marking a closed #475 `[x]` and listing the split-offs #871 and #872 as their own items, which replaces the "Review Findings Carry Their Producer" extension.
- Pending a person: `uv run devops ci` on the delivering tree, which the orchestrating session runs.
- Pending a person: the measurement commands above. After the ConfigMap is applied, `uv run devops ai gateway routes` lists `qwen3-coder:30b` and `gpt-oss:20b` with two deployments each. Every run record of an arm names that arm's group for both analysis and verification (`uv run devops ai runs show <id>`), and `corpus score` prints no `not model-pinned` line. In every session's `profile.json`, every stage's `backends` names only that arm's tiers (ollama-48gib and ollama-64gib, or ollama-16gib and ollama-24gib), which shows that no call fell back to another model and that verification did not reach the pool. The first session of each arm writes a `*-metadata.json` file under its own `.data/475/<arm>/analysis` directory, and every session's `pre_analysis` stage shows 0 LLM calls and no backends. The issue's criterion that the first session shows LLM calls in `pre_analysis` rests on a wrong premise and cannot pass: review pre-analysis never calls a model, and the 8 most recent sessions in the main data directory (20260929-025636 to 20261001-224227) all record `pre_analysis` with 0 LLM calls and no backends.
- Pending a person: the results, added to this file before merge as a table per model that cites a run ID for every figure and states the synthetic caveat (synthetic recall measures regression against the defects the generator injects, not review capability). For each model: found and reported counts per injection with pass^k, pass@k and found-in-none; candidates by verdict; unlabelled findings (reported, matching no injection) by severity; unparsed persona replies; median seconds per candidate and tokens. Then the decision by the rule above, stated in the PR with the rule, and, if a factor is warranted, the follow-up issue linked.
- Not checked when merged: the PR's own remote checks.

## Measurements
New-test durations from `uv run pytest -p no:cacheprovider -q -n 0 tests/test_k8s_llm_gateway.py tests/test_config_env_overrides.py tests/test_run_store.py --durations=0 --durations-min=0` (44 passed, one-minute load about 3 on 16 cores). Setup and teardown each took under 0.005 s, so the figures are the call phase.

| Test | Time |
| :--- | ---: |
| `test_the_environment_pins_review_analysis_and_verification_to_one_model` | 0.08 s |
| `test_a_review_benchmark_can_review_without_static_scanners[off]` | 0.07 s |
| `test_a_review_benchmark_can_review_without_static_scanners[on]` | 0.07 s |
| `test_a_review_model_has_a_group_of_its_review_deployments_alone[qwen3-coder:30b]` | 0.03 s |
| `test_a_review_model_has_a_group_of_its_review_deployments_alone[gpt-oss:20b]` | 0.03 s |
