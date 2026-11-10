# Proposal: #4289

## Why
Every Jev call of `src/devops_cli/ai/jev.py` fails live through the LLM gateway. `SystemOneModel` posts to `{ai.gateway_url}/systemone`, and the gateway answers HTTP 404 for `/v1/systemone`. The `model_list` entry `typesafe/jev-1.14` (`openrouter/typesafe/jev-1.14`) is a chat route, and OpenRouter refuses a decision model on chat completions with HTTP 400. The entry only made the model look healthy in a route listing. Closes #4289.

## What Changes
- `k8s/llm/gateway/config.yaml`: remove the `model_list` entry `typesafe/jev-1.14`. Add the pass-through `POST /v1/systemone` to `https://openrouter.ai/api/v1/systemone` (`auth: true`, `forward_headers: false`, the OpenRouter key from the environment of the gateway).
- `CONST_AI_GATEWAY_HOSTED_MODELS`: remove `typesafe/jev-1.14`. It is no chat group, so it must not be a tier of `roadmap.implement.ladder`.
- The client keeps its code. Its path and body already match (see Feasibility).
- `tests/ai/test_jev_gateway_route.py`: new tests. They fail when the client path and the pass-through differ, when the gateway lists a chat route for Jev, or when the client leaves the documented body.
- `SECURITY.md` rule 13 and `k8s/README.md`: name the route, the key and the live check.
- The change alters a manifest and a requirement, so it carries a spec delta.

It fits one pull request.

## Capabilities
- `roadmap-service-deployment`: MODIFIED requirement "The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models".

## Impact
- The five helpers of `jev.py` can run live through the gateway after Argo CD rolls the ConfigMap. This unblocks #4282 and #4284.
- Jev prompts leave the cluster to OpenRouter. The pass-through cannot add `provider.data_collection: deny` to the body, so the privacy setting of the OpenRouter account applies. The old chat entry set it, but it never served a request.
- The spend ledger of the gateway does not record these calls. OpenRouter reports `usage.cost` in each answer.
- No secret changes: the Secret key `openrouter-api-key` already exists.

## Feasibility
Premise checked on 2026-11-09 against documents, library source and the running system.

1. OpenRouter has two Jev endpoints. `POST /api/alpha/decisions` is the Decisions API (https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request). `POST /api/v1/systemone` is the System One API "for people who already use the TypeSafe SDK" (https://openrouter.ai/docs/guides/community/jev, https://openrouter.ai/docs/guides/community/typesafe-sdk). Both take the OpenRouter key as `Authorization: Bearer`, and both bill to the same account. An unauthenticated `POST` of `{}` to both paths answered HTTP 401 (not 404), so both paths exist.
2. The request body of the Decisions API is `model`, `state`, `questions` (a map of name to `{type, instructions, criteria}` with `type` in `noul`, `choice`, `score`, `box`). The System One guide names the same three required fields and the same question fields. The pydantic-ai `SystemOneModel` (pydantic-ai 2.59.0, `models/system_one.py`) sends exactly `model`, `state`, `questions` (and `temperature` or `extra_body` when set), with the model name `typesafe/jev-1.14`, which OpenRouter uses unchanged.
3. The answer: both documents give `model`, `answers` (a map with `type`, `noul`, `choice`, `probabilities`, `score`, `legend`, `confidence`) and `usage.input_tokens`, `usage.output_tokens`. OpenRouter adds `id`, `provider` and `usage.cost`. `SystemOneModel` reads `model`, `answers` and `usage` and ignores extra fields. `test_the_client_reads_the_answer_that_openrouter_adds_fields_to` proves it with the documented example.
4. Choice of endpoint: the wire format of the code matches both. The change uses `/api/v1/systemone`, because OpenRouter documents it for System One clients, it is not marked alpha (the Decisions API says "the shape may change"), and the client needs no change. The Decisions API would also take `provider.data_collection`, but the gateway cannot change a body, and the client must not send a field that the System One reference does not list.
5. LiteLLM: the pinned image is `ghcr.io/berriai/litellm:v1.103.0`. Its docs (https://docs.litellm.ai/docs/proxy/pass_through) give `general_settings.pass_through_endpoints` with `path`, `target`, `headers` (`os.environ/` allowed), `forward_headers`, `auth`, `methods`, `include_subpath`. The source of the 1.103.0 wheel (`proxy/pass_through_endpoints/pass_through_endpoints.py`) shows that `auth: true` needs no license (`user_api_key_auth` dependency), that `os.environ/` in a header value is resolved from the environment, and that no route `/v1/systemone` exists in LiteLLM.
6. Live proof of the pass-through, offline: LiteLLM 1.103.0 ran locally with this `pass_through_endpoints` entry (target replaced by a local test server, fake keys). A `POST /v1/systemone` with the gateway key reached the upstream at `/api/v1/systemone` with the body unchanged and `Authorization: bearer <the OPENROUTER_API_KEY of the environment>`. A request with no key or a wrong key was not forwarded (the upstream saw one request). A `GET` answered 405.
7. Not verified: a real answer of OpenRouter to `/api/v1/systemone` (it needs the key of the gateway, which this change does not read), and whether that endpoint accepts `provider`. The live check is in the pull request comment.

## Existing Tool Considered
LiteLLM `pass_through_endpoints` covers the need and `SystemOneModel` of pydantic-ai already speaks the protocol, so no code is built. The change deletes the chat route `typesafe/jev-1.14` of `model_list`, its entry in `CONST_AI_GATEWAY_HOSTED_MODELS` and its test. The other options are worse: the direct TypeSafe API needs a new key and an egress rule (a person decides), and dropping Jev removes the planned uses of #4282 and #4284.
