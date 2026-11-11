# Design

## Decisions
- The cached prompt tokens travel on the objects that already carry the token counts: `LLMResponse` for a reply and `StreamUsage` for a stream. The provider mixin reads the reply, and the spend recorders in `unified.py` read these objects.
- The field name is `cache_read_tokens`, the name of `track_request_spend`, the pricing registry and pydantic-ai `RequestUsage`.
- A recorder that estimates the prompt tokens, because the reply names no usage, gives 0 cached tokens.

## Rejected alternatives
- Read the cached tokens in `unified.py` from the provider reply. `unified.py` does not see the provider reply; the mixins build `LLMResponse` and `StreamUsage`.
- Carry the cached tokens in a new context variable. The reply objects already carry the usage, and a context variable adds hidden state.
- Add the direct Claude provider. Its reply names cache reads in a different field (`cache_read_input_tokens`), outside `input_tokens`, and the issue cites the OpenAI-compatible form of the gateway only.
