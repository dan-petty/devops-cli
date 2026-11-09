# Proposal: #4241

## Why

The owner decided on 2026-11-09 to value local AI tokens in the spend reports at the hosted prices of `qwen3.8:27b` (chat) and `qwen/qwen3-embedding-8b` (embeddings) (#4241). The live ConfigMap `devops-cli-config` holds `ai.reference_model` and `ai.reference_embedding_model` with these names, applied by hand. The template `k8s/devops/configmap.example.yaml` names neither. `devops k8s deploy-stack` renders the template, so the next deploy removes the two lines, and the Service reports value local tokens at `gpt-4o` and `text-embedding-3-small` again. The Service ledger showed 2,361 USD hosted equivalent at `gpt-4o` against about 60 USD at `qwen3.8:27b`.

## What Changes

- Add `ai.reference_model: qwen3.8:27b` and `ai.reference_embedding_model: qwen/qwen3-embedding-8b` to `k8s/devops/configmap.example.yaml`, with a comment that gives the owner decision, the date, the two prices and the place of the prices (the file `pricing_overrides.json` of the Service volume).
- Tell the two settings in item 19 of the Roadmap service list in `k8s/README.md`.
- Add the requirement "The ConfigMap template names the reference models" to the capability `roadmap-service-deployment`. A manifest is observable, so the change carries a spec delta.
- Tests: two tests in `tests/k8s/test_k8s_configmap.py`.
- The change does not apply the ConfigMap: the live ConfigMap already holds both lines.
- The change fits one pull request.
- Not in this change: a repository-owned price. The price stays a hand-set file on the volume until #4242 adds a setting for it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: a new requirement for the two reference models in the template.

## Impact

- Manifest: `k8s/devops/configmap.example.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_k8s_configmap.py`
- Deployment: none. The live ConfigMap already holds both lines, so a deploy-stack changes nothing for these keys. The change adds two keys that `AIConfig` declares, and it removes no key, so no rollout order applies. The key-walk test of #4093 (`tests/k8s/test_k8s_configmap_keys.py`) covers both keys.

## Feasibility

- Checked on 2026-11-09 on origin/main `f9e47b7b`. `render_active_devops_configmap` of the template gives `ai.reference_model` `gpt-4o` and `ai.reference_embedding_model` `text-embedding-3-small` (the defaults of `AIConfig`). The new test fails on the base for this reason alone, and the key lookup of the comment test raises `StopIteration` because the template holds no `reference_model` line.
- The live ConfigMap (`kubectl -n devops get configmap devops-cli-config`, read only) holds `ai.reference_model: qwen3.8:27b` and `ai.reference_embedding_model: qwen/qwen3-embedding-8b`. A comparison of the rendering of the template with the live config, key by key, shows three differences: these two keys and `ai.tasks.stage`. The last one is a deliberate pause that a person removes after #4228 merges, and it is not part of this change.
- The Service pod holds `/home/devops/.data/ai/pricing_overrides.json` (volume `roadmap-service-home`) with the two prices: 0.035 and 1.5 USD for `qwen3.8:27b`, and 0.01 and 0 USD for `qwen/qwen3-embedding-8b`, per million tokens.
- genai-prices 0.1.13 raises `LookupError` for `qwen3.8:27b` and for `qwen/qwen3-embedding-8b`, with the provider `openai` and with no provider. So the overrides file is the only source of the price now. `PricingRegistry.get_pricing` reads an override before it asks genai-prices.
- `AIConfig` declares both settings (`src/devops_cli/config/settings.py`), and `resolve_reference_pricing` in `src/devops_cli/ai/spend/ledger.py` reads them.
- No open or merged pull request touches the lines of `ai:` that this change adds. #4228 changes `ai.tasks.stage` in the same file; the two changes do not touch one line.

## Existing Tool Considered

The two settings and `devops ai cost set-price` already exist, so the change needs no new code and no library. `devops ai cost update-pricing --source <file>` writes a snapshot to the same volume, so it does not remove the hand step. A repository-owned price needs new code and is #4242. Cost of this change: about 15,000 tokens to build and review, none to keep, and about 30 minutes. The change deletes no internal code.
