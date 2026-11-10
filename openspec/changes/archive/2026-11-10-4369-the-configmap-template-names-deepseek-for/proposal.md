# Proposal

## Why

Issue #4369: the template `k8s/devops/configmap.example.yaml` sets `claude-sonnet-5-5` with `context_window` 200000 in the slot `ai.tasks.analysis`. The live ConfigMap `devops/devops-cli-config` sets `deepseek-v4.1-flash-1017` with 256000, by the owner decision of 2026-11-10 ("move analysis back to DeepSeek"; a Sonnet trial comes later). `render_active_devops_configmap` renders from the template, so the next render puts Sonnet back. In that slot, Sonnet costs about 67 USD a week.

## What Changes

- Set `ai.tasks.analysis` to `deepseek-v4.1-flash-1017` and `context_window` 256000 in the template, with a comment that names the decision, the cost of the trial and the way to try Sonnet again.
- Add `ai.tasks.stage` to the template with the same model and window, as the live ConfigMap has it. The slot then does not follow `analysis` when a later trial changes `analysis`.
- Change the text that stated the trial: `k8s/README.md` (Roadmap service, item 19), `docs/roadmap/stage.md` and `SECURITY.md` (rule 13).
- Change the tests that pinned the Sonnet value, so they assert DeepSeek and 256000 for `analysis` and `stage`.
- Not changed: `roadmap.implement.ladder` (the template has two tiers, the live ConfigMap has one) and the values that are specific to the live deployment (see Feasibility).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change edits a template and the text and tests that cite it.

## Impact

- `k8s/devops/configmap.example.yaml`, `k8s/README.md`, `docs/roadmap/stage.md`, `SECURITY.md`.
- `tests/config/test_k8s_devops_runtime.py`, `tests/k8s/test_k8s_configmap.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.
- No cluster change. The live ConfigMap is already changed, and Argo CD does not own it.

## Feasibility

Read on 2026-11-10.

- `kubectl -n devops get cm devops-cli-config -o jsonpath='{.data.devops-cli\.yaml}'` (read only) prints `ai.tasks.analysis` with `deepseek-v4.1-flash-1017` and 256000, and an `ai.tasks.stage` entry with the same two values.
- A comparison of the flattened keys of the live ConfigMap and of the template lists these differences before the change: `ai.tasks.analysis.model` and `context_window`, `ai.tasks.stage.*` (live only), `roadmap.implement.ladder.edit` and `.repair` (the template adds `claude-sonnet-5-5` as tier 2, added in #4275), `roadmap.stage.jev_screen` (template only, default `off`), `service.drain_timeout_seconds`, `service.poll_interval_seconds` and `service.github_requests_per_hour` (live only), and `service.repos` and `service.github_app` (placeholders in the template, real values in the live ConfigMap). The keys `ai.reference_model`, `ai.reference_embedding_model`, `ai.price_overrides`, `search.searxng_url`, `crawl4ai.url`, `roadmap.mcp.url` and the other `ai.tasks.*` are equal.
- `render_active_devops_configmap` reads the template (`src/devops_cli/k8s/configmap.py`), so the template decides what a re-render writes.
- The gateway group `deepseek-v4.1-flash-1017` has `max_input_tokens` 1048576 in `k8s/llm/gateway/config.yaml`, so 256000 fits.

## Existing Tool Considered

No tool is needed: this edits one template and the text that cites it.
