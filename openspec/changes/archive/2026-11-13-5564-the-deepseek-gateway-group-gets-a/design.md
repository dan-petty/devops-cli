# Design

## Decisions
- **Fallback to the undated model through the same provider.** The owner chose `openrouter/deepseek/deepseek-v4.1-flash` (2026-11-13). The undated model has its own provider list, and with no `floor` route OpenRouter balances a call across its providers and avoids a provider that fails.
- **Keep the provider filter.** The fallback asks for fp8 weights and `data_collection: deny`, as the dated group does, so the fallback weakens no privacy control.
- **Price at the list price.** The providers of the undated model charge from 0.05 to 0.45 USD per million input tokens. The list price is the top of that range, so the spend counters do not read low. OpenRouter reports the real cost of each call.

## Rejected alternatives
- **A Claude or Gemini group as the fallback.** The prompt would leave the cluster to a second provider, and the cost is higher. The owner chose the DeepSeek model.
- **The local `qwen3.8:27b` group as the fallback.** Its window is 262,144 tokens, and stage requests reach about 293,000 input tokens. SECURITY.md item 13 also forbids a fallback between a hosted group and a group that is not hosted.
- **Remove the `floor` route of the dated group.** The `floor` route keeps the normal cost low. The fallback covers the time when the cheapest provider fails.
