# Design

## Decisions
- One route serves the client and the Service: `POST {ai.gateway_url}/systemone`, a LiteLLM pass-through to `https://openrouter.ai/api/v1/systemone`. The path is the path that `SystemOneModel` already uses, so the client code does not change.
- The pass-through sets `auth: true`. The gateway is reachable from outside the cluster, and an open pass-through would let anyone spend the OpenRouter key. LiteLLM 1.103.0 needs no license for it.
- `forward_headers: false` and a fixed `Authorization` header from `os.environ/OPENROUTER_API_KEY`. The gateway key of the caller never reaches OpenRouter.
- `methods: [POST]` and `include_subpath: false`: the route serves one call and nothing else.
- Jev is removed from `model_list` and from `CONST_AI_GATEWAY_HOSTED_MODELS`. It is no chat group; a chat call always fails, and a ladder tier named `typesafe/jev-1.14` would fail the same way.
- The check is `tests/ai/test_jev_gateway_route.py`. It builds the model as the bridge builds it, records the path of the request on the HTTP fake, and compares that path with the pass-through of the real gateway config (target, auth, headers, methods). It also fails when `model_list` lists the model again.

## Rejected alternatives
- Pass-through to `/api/alpha/decisions`: the wire format also matches, but OpenRouter marks it alpha and the shape may change. The pydantic-ai issue 8552 only verified that rewrite offline. The System One path is documented for this client.
- Direct call to `api.typesafe.ai` (`CONST_URL_TYPESAFE_API_BASE`): it needs a new key and an egress decision. A person decides both, and the pass-through needs neither.
- Keep the `model_list` entry next to the pass-through: it serves chat calls, which OpenRouter answers with HTTP 400 (evidence of #4289), so it only makes the model look healthy.
- Drop Jev: it removes the planned uses of #4282 and #4284, and the route works with documented, existing tools.
