## ADDED Requirements

### Requirement: Hosted groups call a provider with an optional key
The gateway config SHALL serve the groups `gemini-3.8-flash`, `claude-sonnet-5-5` and `claude-haiku-5-5`. Each SHALL name a `gemini` or `anthropic` backend with no `api_base`, set its window, and read its key from a variable of the gateway Deployment that is an optional key of the Secret `llm-gateway-secrets`.

#### Scenario: A hosted group without its key
- **WHEN** the gateway starts with no `GEMINI_API_KEY`
- **THEN** it serves every group, and a call to `gemini-3.8-flash` fails with an error that names the missing key

### Requirement: A Claude group sets its prices and drops refused parameters
A Claude group SHALL set its input and output prices, because the cost map of the pinned image lacks the model. It SHALL drop `temperature`, `top_p` and `top_k`, which the provider API refuses.

#### Scenario: A Claude call with sampling parameters
- **WHEN** a caller sends `temperature` and `top_p` to `claude-sonnet-5-5`
- **THEN** the request to the provider holds neither

### Requirement: The gateway reaches providers on port 443 only
The gateway NetworkPolicy SHALL admit TCP 443 to public addresses for hosted calls. It SHALL exclude every private, carrier-grade NAT and metadata range, and it SHALL hold no other ipBlock.

#### Scenario: A widened egress rule
- **WHEN** the hosted egress rule gains port 80, loses a private range from its exclusions, or another ipBlock is added
- **THEN** the egress check fails

### Requirement: Hosted groups join no pool
No pool, fallback, context-window fallback or routing group of the gateway config SHALL name a hosted group, so a prompt leaves the cluster only when its caller names the group.

#### Scenario: A fallback to a hosted group
- **WHEN** a fallback chain names `claude-haiku-5-5`
- **THEN** the hosted-group check fails
