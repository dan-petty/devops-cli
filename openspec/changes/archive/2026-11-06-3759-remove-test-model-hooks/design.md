# Design

## Context

Two flags named `ALLOW_MODEL_REQUESTS` exist: one in `ai/agents/agent.py`, one in `ai/agents/testing.py`. Both default to `True`. Only tests set them. `ai/agents/testing.py` holds a `TestModel` and a `FunctionModel` that duck the `LLMClient` verbs `chat` and `chat_messages`, so the hand-rolled loop `PydanticAgent` can run on them. The same module holds `capture_run_messages`, which reads a `ContextVar` that the loop fills.

The project already has the model seam (ADR 0007): the factory `_client_override` that the `model_fake` fixture installs. `ModelFake` answers `chat_messages`, queues answers and records each call.

## Decisions

- **Delete the module, not the flag only.** Without the flags nothing else in `testing.py` has a caller in `src`. A module that only tests import is a test accommodation in `src`.
- **Use `model_fake` for the agent tests.** `agent.override(model=model_fake)` swaps the client for the fake, and `model_fake.answer(...)` sets the reply. The test also reads the request from `model_fake.requested`.
- **Drop the tests of the removed utilities.** The tests of `TestModel`, `FunctionModel`, `capture_run_messages`, and the flag test code that no longer exists. Their behavior was the hook itself. The behavior that remains (`Agent.override` of the model and of the toolsets) keeps a test.
- **No new test for the refusal of a real model.** The hermetic floor already fails a test that reaches a model without a fake (#1310). A second refusal in the product is the switch this change removes.
- **Keep `resolve_pydantic_ai_model("test")`.** It maps the name `test` to pydantic-ai's own `TestModel`, as pydantic-ai does. It is not test detection, and a test of it stays in `test_pydantic_agent.py`, which #2489 owns.

## Rejected alternatives

- **Keep `TestModel` and `FunctionModel` in `tests/support/`.** `ModelFake` and pydantic-ai's own `TestModel` and `FunctionModel` cover every use. A second home-made model would repeat them.
- **Wait for #2489.** #2489 deletes `PydanticAgent` and the files that test it. This change touches none of those files, and the switch is a product risk now.
