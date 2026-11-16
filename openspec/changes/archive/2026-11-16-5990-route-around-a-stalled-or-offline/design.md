# Design

## Decisions
- One group with two orders, not only a fallback group. LiteLLM 1.103.11 removes cooled and unhealthy deployments before it keeps the lowest order, so a call reaches order 2 before it is sent. A fallback starts only after a call fails, and an in-stream 408 starts none.
- Order 1 sets `allowed_fails: 0`. With the router value the failures must come within `cooldown_time`, and calls that each stall for 300 s never do. One failure cools it. A client that goes away from a call of order 1 does not cool it: on the mock proxy the next two calls went to order 1.
- Order 1 sets `cooldown_time: 120`, at least the check interval (60 s) plus the check time (30 s), so a check ends inside the cooldown and a deployment that still stalls stays out. A test holds this order.
- Each checked deployment sets `health_check_timeout: 30`. The default is 60 s, the same as the interval, so a stalled check would make the cycle 120 s.
- `router_settings.allowed_fails: 2`. At 3 (the default) the router counts no failures and never cools a group with one deployment. Against a mock Ollama tier that refused connections, each call took 25 s before its fallback; at 2 the first call cooled the tier in 2.1 s.
- Health checks cover `deepseek-v4.1-flash-1017` and `deepseek-v4.1-flash` only. No Ollama group, because a check takes the one slot of a tier (#5302). The checks of the one-deployment group route nothing, but they give its health in `/health` for #5967.
- Keep the fallback to `deepseek-v4.1-flash`. Mock: with order 1 stalled and order 2 cooled after 3 failures, the fallback answered in 0.34 s; without it the call failed with "No deployments available". An in-stream 504 on order 1 went to order 2 with and without the fallback, so that case does not need it.
- Keep `_HOSTED_GROUP_PRICES` as it is: it already has a key for each deployment model and the `:floor` key. The price test now checks each deployment, not one deployment for each group.

## Rejected alternatives
- `allowed_fails_policy` with `TimeoutErrorAllowedFails: 0`: the cooldown callback gets the raw `OpenRouterException`, so the policy did nothing in the mock.
- A gateway callback that ends a stream with no first chunk: on 1.103.11 the router returns the stream first, so a callback cannot fall back.
- Health checks on all groups: a check takes the one slot of an Ollama tier.
- Remove the fallback: a call while both deployments are cooled then fails at once.

## Known limits (later steps of #5990)
- No first-token deadline: a call in flight when a stall begins fails after the stall, and the client sends it again (#5965).
- A run of an agent that order 2 answers records the price of order 1, because the reply body names the group. A request flag that returns the deployment model would fix it.
- No metric or alert names a stalled group yet (step 2).
