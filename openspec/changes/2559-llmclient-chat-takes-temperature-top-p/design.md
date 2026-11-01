# Design

## Decisions

- **Pass the values through; do not remove the parameters.** Review group analysis passes `temperature`, `top_p` and `seed` and needs them on the wire. The OpenAI-compatible API, Ollama and the Anthropic API take sampling per request. `chat` and `chat_messages` name the three parameters, so any other keyword is a `TypeError`.
- **One `CallSampling` value, not three parameters per hop.** `CallSampling` is a `NamedTuple` of `temperature`, `top_p` and `seed`, all `None` by default, in `src/devops_cli/ai/client/models.py`, next to `ServedByAuthority`. `chat_messages` builds it once. Every internal function from `_retry_chat_dispatch` to the payload builder takes `sampling: CallSampling | None = None`. A builder that gets `None` behaves as it does today.
- **A per-call value replaces the configured one when it is not `None`.** `temperature` and `top_p` fall back to the config. `seed` has no config field, so with no per-call seed the request has no seed.
- **The existing gate wins over a per-call value.** The spec says `use_model_sampling` leaves sampling to the model, and a reasoning model of the OpenAI-compatible driver takes no sampling. A per-call value does not override either gate. Claude keeps its own gate (the model declares sampling, no adaptive thinking, and not `use_model_sampling`). The reply cache key already sets `temperature` and `top_p` to `None` under `use_model_sampling` or `supports_reasoning`, so a value that the request omits does not split the cache.
- **The seed uses the same gate as `temperature` and `top_p`.** It is a sampling parameter, and the setting says "leave sampling parameters to the model". This is why the description of `use_model_sampling` names the seed too. Each driver puts the seed where its API takes it: `seed` in the OpenAI-compatible parameters, `seed` in the Ollama `options`.
- **Claude never gets a seed.** The Messages API has no seed (the installed SDK has no such parameter). The Claude request keeps its `extra_body` path for `temperature` and `top_p`.
- **The cache key holds `seed` only when a seed is sent.** `chat_messages` adds a `seed` key to the options hashed by `generate_key` only for a per-call seed that is not `None` and not under the gate. A call with no seed hashes the same options as today, so no stored reply is lost. A Claude call with a seed also hashes it, though Claude drops it. That is one extra miss and never a wrong hit, and it avoids a provider test in the key.
- **Groups go provider by provider.** `_invoke_provider_messages` passes `sampling` to one driver per group, so every group ends with a passing test suite. Until group 2 and group 3, the Ollama and Claude drivers do not get the value. No group-1 test relies on them.

## Rejected alternatives

- **Remove `**kwargs` and take no sampling.** `src/devops_cli/review/analysis.py` line 1079 passes all three on each call, and the fix of #2447 made the record name the configured sampling. A `TypeError` there would stop group analysis.
- **A per-call value replaces the whole config sampling.** A caller that sets only `temperature` would lose the configured `top_p`. The call sites that pass one value would need to pass all.
- **A per-call value overrides `use_model_sampling`.** The spec "Model-level sampling option" and the setting description say the request carries no `temperature` or `top_p`. An override would break that requirement for every task that sets the flag.
- **Pass the three values through a `ContextVar`, as `reply_schema` does.** It would add no parameter to the internal functions. It hides the input of the payload builders in implicit state, and the explicit chain is what the refine design of the issue chose.
- **Thread `temperature`, `top_p` and `seed` as three parameters through every function.** It changes the same signatures and triples the lines for no gain. The earlier attempt of the implement job ran out of its request limit on this edit.
- **Give `AIConfig` a seed field for the fallback.** No criterion of the issue asks for it, and it adds a setting, its document and its validation.
