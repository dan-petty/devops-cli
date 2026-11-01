## MODIFIED Requirements

### Requirement: Model-level sampling option
The system SHALL support a `use_model_sampling` boolean setting in `AIConfig` and `AITaskOverride`. When enabled for a task, requests SHALL omit `temperature`, `top_p` and `seed` on both gateway and native Ollama paths, including values that a caller passes per call.

#### Scenario: use_model_sampling omits temperature and top_p
- **WHEN** a task enables or inherits `use_model_sampling`
- **THEN** outbound request payloads for that task carry neither `temperature` nor `top_p`

#### Scenario: use_model_sampling ignores per-call sampling
- **WHEN** a task enables `use_model_sampling` and a caller invokes `client.chat` with `temperature=0.9`, `top_p=0.8` and `seed=7` against a fake model at the HTTP edge
- **THEN** the request body carries none of `temperature`, `top_p` and `seed`

### Requirement: Reply cache key includes request sampling
The system SHALL include `temperature`, `top_p`, `reasoning_effort`, and reply cap in the options hashed by the response cache key. A `temperature` or `top_p` that a caller passes per call SHALL replace the configured value in those options. A `seed` that a caller passes SHALL join the options. Under `use_model_sampling` the options SHALL hold none of the three per-call values.

#### Scenario: Cache keys partition different temperatures
- **WHEN** two requests with identical messages are dispatched with differing temperatures
- **THEN** each request produces a distinct cache key and dispatches to the model

#### Scenario: Cache keys partition per-call temperatures
- **WHEN** a caller invokes `client.chat` twice with the same system and user text, once with `temperature=0.1` and once with `temperature=0.9`
- **THEN** both calls reach the fake model at the HTTP edge

#### Scenario: Cache keys partition per-call temperatures of a reasoning model on Ollama
- **WHEN** a client for provider `ollama` has `supports_reasoning` set, and a caller invokes `client.chat` twice with the same system and user text, once with `temperature=0.1` and once with `temperature=0.9`
- **THEN** both calls reach the fake Ollama server at the HTTP edge

#### Scenario: Cache keys partition per-call seeds
- **WHEN** a caller invokes `client.chat` twice with the same system and user text, once with `seed=7` and once with `seed=42`
- **THEN** both calls reach the fake model at the HTTP edge

#### Scenario: Equal per-call sampling hits the cache
- **WHEN** a caller invokes `client.chat` twice with the same system and user text and `temperature=0.9`
- **THEN** only the first call reaches the fake model at the HTTP edge

## ADDED Requirements

### Requirement: Per-call sampling reaches the request
The system SHALL send the `temperature`, `top_p` and `seed` that a caller passes to `LLMClient.chat` or `LLMClient.chat_messages` in place of the configured values, subject to the requirement "Sampling gates win over per-call sampling". A parameter that the caller omits SHALL take the configured `temperature` or `top_p`. The system SHALL send no `seed` when the caller passes none.

#### Scenario: Gateway request carries per-call sampling
- **WHEN** a client for provider `gateway` has `temperature` 0.1 and a caller invokes `client.chat("sys", "user", temperature=0.9, seed=7)` against a fake model at the HTTP edge
- **THEN** the request body carries `temperature` 0.9 and `seed` 7

#### Scenario: Omitted parameters keep the configured values
- **WHEN** a client for provider `gateway` has `temperature` 0.1 and `top_p` 0.95 and a caller invokes `client.chat("sys", "user")` against a fake model at the HTTP edge
- **THEN** the request body carries `temperature` 0.1 and `top_p` 0.95 and no `seed`

#### Scenario: Native Ollama request carries per-call sampling
- **WHEN** a client for provider `ollama` has `temperature` 0.1 and a caller invokes `client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7)` against a fake Ollama server at the HTTP edge
- **THEN** the `options` of the request body hold `temperature` 0.9, `top_p` 0.8 and `seed` 7

#### Scenario: Claude request carries per-call temperature
- **WHEN** a client for provider `claude` has `temperature` 0.7, its model declares sampling support, and a caller invokes `client.chat("sys", "user", temperature=0.9)` against a fake Anthropic server at the HTTP edge
- **THEN** the request body carries `temperature` 0.9

### Requirement: Claude requests carry no seed
The system SHALL omit `seed` from every Claude request, because the Anthropic Messages API takes no seed, even when a caller passes one.

#### Scenario: Caller passes a seed to Claude
- **WHEN** a client for provider `claude` has a model that declares sampling support and a caller invokes `client.chat("sys", "user", seed=7)` against a fake Anthropic server at the HTTP edge
- **THEN** the request body has no `seed` key

### Requirement: Chat refuses an unknown keyword argument
The system SHALL raise `TypeError` when a caller passes `LLMClient.chat` or `LLMClient.chat_messages` a keyword argument that is not a named parameter.

#### Scenario: Caller passes an unrecognized keyword
- **WHEN** a caller invokes `client.chat("sys", "user", unknown_param=1)`
- **THEN** a `TypeError` is raised and no request is sent

### Requirement: Sampling gates win over per-call sampling
The system SHALL send no per-call `temperature`, `top_p` or `seed` when the request omits sampling. The request omits sampling under `use_model_sampling`, for a reasoning model of the OpenAI-compatible driver, and for a Claude model that declares no sampling support or runs adaptive thinking.

#### Scenario: Reasoning model takes no per-call sampling
- **WHEN** a client for provider `gateway` has `supports_reasoning` set and a caller invokes `client.chat("sys", "user", temperature=0.9, top_p=0.8, seed=7)` against a fake model at the HTTP edge
- **THEN** the request body carries none of `temperature`, `top_p` and `seed`

#### Scenario: Claude model without sampling support takes no per-call sampling
- **WHEN** a client for provider `claude` has a model that declares no sampling support and a caller invokes `client.chat("sys", "user", temperature=0.9, top_p=0.8)` against a fake Anthropic server at the HTTP edge
- **THEN** the request body carries neither `temperature` nor `top_p`
