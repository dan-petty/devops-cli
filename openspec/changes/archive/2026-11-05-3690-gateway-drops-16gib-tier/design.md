# Design

## Decisions

The README column **Serves** is the one record of the tiers that serve. The existing test reads this column and names each consumer to move, so the change starts with the column, and the test shows the rest of the work.

The DaemonSet stays, with one setting changed. The rule that the test holds says that a tier keeps one model, and that only a chat tier that the gateway sends embeddings to keeps two. The tier now gets no embeddings, so it sets 1. A revert of the change restores 2 with the routes.

The devcontainer moves to `ollama-48gib` with `qwen3.8:27b`. The tier loads that model and no other model, so the setting cannot cause an eviction.

## Rejected alternatives

- Move `gpt-oss:20b` or the order 2 embedding deployment to `ollama-48gib` or `ollama-64gib`. Rejected: `test_the_48gib_and_64gib_tiers_load_qwen_alone_at_its_native_context` and the requirement that those tiers load one model refuse it, and a second model drops the KV cache (#3567).
- Keep `OLLAMA_MAX_LOADED_MODELS` at 2 and exempt the tier in the test. Rejected: an exemption makes the check read a false rule. The value 1 keeps the rule true with no exemption.
- Delete the DaemonSet or set a node selector that matches nothing. Rejected: the tier must come back by a small revert, and the pod does no harm with no client.
- Depend on the cooldown of the router (`allowed_fails`, `cooldown_time`). Rejected: a deployment returns after 30 s, so each review on a down host loses time again, and the cordon alone does not take the deployment away.
