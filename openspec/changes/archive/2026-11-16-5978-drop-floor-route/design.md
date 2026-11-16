# Design

## Decisions
- Remove `:floor` from the deployment model and from the alias, and change nothing else in the group. The filters `quantizations: [fp8]` and `data_collection: deny` stay, and the fallback group `deepseek-v4.1-flash` stays.
- Keep the price of the group until OpenRouter has reported one day of cost on the new route. A price from a guess of the routing would be less correct than the measured flex rate.
- Keep the pricing key of the `:floor` route, so the spend records of that route keep a price.
- A test of the gateway manifest refuses a `:floor` route, so the cause cannot come back without a decision.

## Rejected alternatives
- `provider.preferred_max_latency` with `:floor`: it moves a slow endpoint to the end of the list but does not exclude it, and the owner asked to remove each cause of a job failure now.
- `provider.ignore` of the flex providers: the list of flex endpoints changes, so the list needs care for each new provider.
- A fallback group: LiteLLM 1.103.11 raises an in-stream 408 with no fallback (#5965), so a fallback does not start.
