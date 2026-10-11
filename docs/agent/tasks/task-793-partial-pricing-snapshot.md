# Task: Fix Partial Pricing Snapshot Merge and Expiry (#793)

**Issue**: [#793](https://github.com/dan-petty/devops-cli/issues/793)
**Status**: Done
**Milestone**: v0.2.34
**Priority**: priority/p1-high
**Scope**: scope/ai
**Feasibility**: Passed

## Description
When updating the AI model pricing catalog via a custom source or remote registry, a partial snapshot previously replaced the entire catalog, discarding models and providers not present in the snapshot. Additionally, cached pricing snapshots lacked versioning metadata, causing snapshots to persist indefinitely even across updates to `genai-prices`. This change ensures partial snapshots merge field-by-field onto the bundled dataset of installed `genai-prices`, records `genai_prices_version` and fetch timestamps to invalidate snapshots across package updates, passes the recorded fetch timestamp into `DataSnapshot`, adds `--reset` to `devops ai cost update-pricing`, introduces `--format yaml` with base-rate table headers and captions to `devops ai cost list-pricing`, and updates `SpendGuard.record_usage` and `EmbeddingResult.cost` to price dynamically with tiered request pricing.

## Key Changes
- **Pricing Registry** (`ai/spend/pricing.py`):
  - Added `UpdatePricingResult` namedtuple returning `source_model_count` and `merged_model_count`.
  - Added `_merge_single_provider` and `_merge_providers` to perform field-by-field merging of provider definitions onto bundled data, placing file models first and unbundled providers after bundled providers.
  - Implemented metadata wrapping for persisted snapshots recording `genai_prices_version` and UTC `fetched_at`.
  - Added version validation in `_load_persisted_snapshot()`: if the snapshot's recorded version does not match the installed `genai-prices` version or is unreadable/corrupt, logs a warning instructing the user to run `devops ai cost update-pricing --reset` and falls back to bundled data.
  - Ensured `DataSnapshot` receives the recorded fetch timestamp as `timestamp` (`auto_update_timestamp`) rather than current load time.
  - Removed dead `isinstance(fetched, DataSnapshot)` branch in `update_from_remote`.
  - Added `reset_pricing()` to delete `<data>/ai/pricing_snapshot.json` and clear process-wide and registry caches.
- **AI Cost CLI Commands** (`commands/ai_cost.py`):
  - Updated `devops ai cost update-pricing`: added `--reset` option; enforced mutual exclusion with `--source` (`BadParameter` usage error); outputs count of models supplied by source and total in merged catalog.
  - Updated `devops ai cost list-pricing`: added `--format yaml` support; updated table headers to `Base Prompt USD / 1M` and `Base Completion USD / 1M`; added table caption and command help explaining base-tier rates for small calls.
- **Output Subsystem** (`output/console.py`, `output/formatters/tables.py`, `output/models.py`):
  - Added `caption` parameter propagation through table rendering.
  - Added `emoji=False` to `write_stream` in `output/console.py` to prevent Rich from corrupting raw text outputs containing colons (e.g. `:free:`).
- **Spend Guard & Embeddings** (`ai/agents/spend.py`, `ai/agents/embeddings.py`):
  - Updated `SpendGuard.record_usage` to compute request costs using `calculate_request_cost` with request timestamp, while honoring caller-supplied flat rate pricing rules without querying registry.
  - Updated `EmbeddingResult.cost()` fallback to invoke `calculate_request_cost(self.model_name, self.usage.input_tokens or 0, 0, provider=self.provider_name, request_timestamp=self.timestamp)`.

## Decisions
- Merging is performed at the Pydantic/Provider object layer rather than raw JSON to validate schema invariants and maintain typing consistency.
- Snapshot fetch time is stored as an ISO-8601 UTC string and parsed back to a timezone-aware UTC datetime.
- When an obsolete or version-mismatched snapshot is detected, it is ignored safely with a warning and bundled definitions are restored without crashing the command.

## Acceptance Criteria
- [x] Partial snapshot merges onto bundled data of installed `genai-prices`. For its own model ids, snapshot prices win; other bundled models keep their prices.
- [x] Provider fields merge field-by-field: fields left out retain bundled values (`pricing_urls`, `description`, `price_comments`, `model_match`, `provider_match`, `extractors`, `fallback_model_providers`).
- [x] Within a merged provider, file models come first and bundled models with other ids follow. Unbundled providers go after bundled providers in file order.
- [x] Token extraction survives a partial snapshot (`pydantic_ai.usage.RequestUsage.extract` returns 20000 input and 2000 output tokens for both unbundled provider and partial openai file).
- [x] Snapshot file records `genai_prices_version` and fetch time (`fetched_at`). Snapshot is not loaded (falls back to bundled data) if recorded version != installed version or missing.
- [x] Loaded snapshot passes recorded fetch time to `DataSnapshot` as `timestamp` (`auto_update_timestamp`), not load time.
- [x] When snapshot is ignored (stale, old format, unreadable), one warning is logged naming file, reason, and `devops ai cost update-pricing --reset`.
- [x] `devops ai cost update-pricing --reset` deletes `<data>/ai/pricing_snapshot.json` and clears process-wide snapshot and registry caches. Exits 0 if file absent. `--reset` with `--source` is a usage error.
- [x] `update-pricing` reports how many models source supplied and how many merged catalog holds.
- [x] Full snapshot loaded with `--source` works offline with no network.
- [x] Dead `DataSnapshot` branch in `update_from_remote` is removed. Default update path tested with `httpx2.get` stubbed, checking file written and reloaded.
- [x] `list-pricing` headings (`Base Prompt USD / 1M`, `Base Completion USD / 1M`), caption, and command help state rates are base-tier rates for a small call at current time, each call priced from own usage and request time. `--format yaml` prints YAML with same content as `--json`.
- [x] `SpendGuard.record_usage` prices with `calculate_request_cost` at request time (`request_timestamp` optional, defaults now). Caller's `pricing` mapping keeps flat rate without querying registry. Test: `claude-sonnet-4-5` at 250K/1K tokens records 1.5225.
- [x] Embeddings cost fallback prices with `calculate_request_cost(model, input_tokens, 0, provider=self.provider_name, request_timestamp=self.timestamp)`. Local provider costs 0 unless overridden.
- [x] Autouse fixture resets process-wide snapshot after every pricing test. Persistence test clears process-wide snapshot before building second registry.
- [x] Item 4: `PricingRegistry()` from linked worktree subdirectory reads overrides from main worktree's data directory.
- [x] Item 5: `_calculate_days_active` with two days of data and `days_filter=30` returns 2.0.
- [x] Item 6: With clock pinned, `--days` excludes a record from earlier on cutoff calendar day than cutoff.
- [x] Item 7: `_add_column` does not raise for existing column; `_init_db` succeeds when column check is stale.
- [x] Item 8: Ledger with record from today and 3 days ago: `devops ai cost report --format prometheus --days 1 --hardware-cost 1000` omits older model from `requests_total` and prints `devops_cli_ai_hardware_cost_usd 1000.00`. Counterfactual spend changes with `--reference-model`. Bare `devops ai cost --format prometheus` behaves same way.
- [x] `uv run devops ci` passes locally.

## Not in this item
- Remote pricing snapshot scraping scheduler: handled via external cron or manual triggers.
