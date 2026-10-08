# Task: Upgrade pydantic-ai to 2.54.0, past three advisories that fail the devops ci audit (#1446)

**Issue**: [#1446](https://github.com/dan-petty/devops-cli/issues/1446)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p0-critical
**Scope**: type/security, scope/ai, scope/security

## Description

`pyproject.toml` pinned `pydantic-ai==2.35.0`. Three advisories against that version (GHSA-4x9p-g9wm-8q7f, GHSA-fpf4-vwcp-v4hp, GHSA-vmxc-h2x2-jmf3) made `uv audit` fail on every branch, and with it `uv run devops ci` and the pre-push gate. The pin is now `pydantic-ai==2.54.0`, the latest 2.x release. `uv lock --upgrade-package` moved pydantic-ai, pydantic-ai-slim, pydantic-evals and pydantic-graph to 2.54.0. The resolver also requires anthropic 1.5.0 → 1.12.1, openai 3.13.0 → 3.26.1 and google-genai 2.23.0 → 2.29.0. No other package in the lock changes.

devops-cli imported private pydantic-ai modules, and 2.54.0 removed or changed some of them. Each private import, and what replaced it:

| Private import (2.35.0) | In 2.54.0 | Replacement |
| :--- | :--- | :--- |
| `pydantic_ai._cost.best_effort_price` (`ai/result`) | module removed | `genai_prices.calc_price`, a direct dependency already used by `ai/spend/pricing.py`. `calculate_usage_cost` returns its `PriceCalculation`, or None on `LookupError`/`ValueError`, the two errors pydantic-ai treats as "cannot price". |
| `pydantic_ai._output` (`OutputSchema`, `OutputValidator`, `TextOutputSchema`, `run_image_process_hooks`, `run_output_with_hooks`) and `pydantic_ai._sync_stream.SyncStreamBridge` (`ai/result`) | still present | Removed. Nothing in devops-cli used them; they were only re-exported from `ai`, `ai.agents`, `ai.agents.pydantic_agent` and `ai.result`. |
| `pydantic_ai._function_schema._is_call_ctx`, monkey-patched in `ai/agents/context.py` so tool schemas accepted the devops `RunContext` subclass | renamed `is_call_ctx`; the patch's `getattr` guard made it a silent no-op | Patch removed. pydantic-ai recognises only its own `RunContext` as a context annotation. `PydanticAgent`'s `load_capability` tool annotates its context with it and narrows to the devops subclass with `isinstance`, as `harness/workflow.py`'s `delegate_task` already did. |
| `pydantic_ai.durable_exec._base.BaseDurabilityCapability` and `pydantic_ai.durable_exec._runtime_toolsets.RuntimeToolsetKind` (`ai/durable.py`, `tests/test_pydantic_ai_durable.py`) | `BaseDurabilityCapability` is public in `pydantic_ai.durable_exec` and has become pydantic-ai's durable engine builder, with an abstract `get_durable_operation_backend` | `LocalDurabilityCapability` follows pydantic-ai's durable backend guide. An `engine_spec` (`DurabilityEngineSpec`: engine Local, unit step, container run, `wrapped_toolset_kinds=frozenset()`) replaces the private ClassVars. `get_durable_operation_backend` returns `_LocalOperationBackend`, a `JournalCallableOperationBackend` whose `execute` awaits the body in place. The overrides of the private `_bind_to_agent`, `_wrap_leaf_toolset` and `_dispatch_event_stream_event` are gone, because the base now owns them and the empty `wrapped_toolset_kinds` keeps toolsets unwrapped. `before_model_request` delegates to the base's, which validates the request. |
| `pydantic_ai._enqueue` (`EnqueueContent`, `PendingMessage`, `PendingMessagePriority`) (`ai/run`) | still present | Imported from `pydantic_ai.run`, where pydantic-ai documents them. That module has no `__all__`, so a `[[tool.mypy.overrides]]` entry sets `implicit_reexport` for `pydantic_ai.run` alone. mypy still reports a name the module lacks. |
| `pydantic_ai._instrumentation.current_otel_traceparent` (`ai/run`) | still present, undocumented | `get_active_traceparent` reads the active span through OpenTelemetry's `TraceContextTextMapPropagator`, and the re-export is removed. |

`ai/tools`' `DeferredToolRequests.build_results` override now takes `approvals` as a `Mapping`, because pydantic-ai widened the parameter.

**What remains private, for #1001 to retire:**
- `pydantic_ai._ssrf` in `core/validation.py` (`_PRIVATE_NETWORKS`, `is_cloud_metadata_ip`, `is_private_ip`) and `http/egress.py` (`is_cloud_metadata_ip`). pydantic-ai exposes no public SSRF classifier; only its `web_fetch` tool and model downloads use this module. Replacing it would mean choosing another SSRF library or hand-rolling the classification, which is a redesign. The shared classifier is also what keeps the URL pre-flight checks and the connect-time egress check in agreement. The 2.54.0 module contains the GHSA-vmxc-h2x2-jmf3 fix, so both checks get it. `tests/test_validation.py`'s contract test guards the names.
- `LocalDurabilityCapability.resolve_model_id_sync` reads the base's private `_models_by_id`. pydantic-ai's public equivalent is the async `resolve_model_id`.
- `CONST_OPENAI_FINISH_REASONS` and `CONST_ANTHROPIC_STOP_REASONS` in `config/constants.py` are copies of pydantic-ai's private finish-reason maps, not imports. The maps are identical in 2.54.0, and the comment now names that version.

**Behaviour that changed with the library:**
- `LocalDurabilityCapability` now passes its event stream handler to pydantic-ai, whose `EventStreamHandler` type requires an async handler. The old private override also accepted a sync handler; that support is gone.
- pydantic-ai refuses a second durability capability on one agent (`UserError`).
- A tool whose context is annotated with the devops `RunContext` subclass fails pydantic-ai's schema generation.
- The devops `RunContext` subclass and the in-house `PydanticAgent` loop that builds it are #1001's to retire.

## Acceptance Criteria

- [x] `uv audit` reports no pydantic-ai advisory, and `uv run devops ci` passes.
- [x] `pyproject.toml` and `uv.lock` agree. The lock changes only the four pydantic-ai packages and the anthropic, openai and google-genai versions the resolver requires.
- [x] `changelog.d/1446.md` records the upgrade under `### Security`, with the API changes under `### Changed` and `### Removed`. `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- [x] The only private pydantic-ai imports left in `src` are the two `pydantic_ai._ssrf` imports listed above. There are no version checks, `ImportError` fallbacks or copied internals.
- [x] Tests change only where the API changed:
  - `tests/test_pydantic_ai_durable.py` imports `BaseDurabilityCapability` from `pydantic_ai.durable_exec`.
  - `test_local_durability_delivers_run_events_and_leaves_toolsets_unwrapped` replaces the test that called the private `_dispatch_event_stream_event` and `_wrap_leaf_toolset`. It runs an agent on `TestModel` and checks that the async handler receives the tool call and result events, that `get_wrapper_toolset` leaves every toolset unwrapped, and that the steps are recorded.
  - The extended-options test uses `StepPersistence` as its extra capability, since a second engine is refused.
  - Three test tools annotate their context with pydantic-ai's `RunContext`.
  - The result and run tests drop the removed names, and `test_get_active_traceparent` pins the traceparent of a known span context and None outside a span.
  - No test reaches the network, and each one finishes in under 1 s.
- [x] The knowledge base pages that named 2.35.0 (`libraries/pydantic_ai.md`, `python_packages.md`) name 2.54.0, and `uv run devops docs generate --sync-readme` leaves the generated docs unchanged.

## Deliverables

- [x] Pin and lock: `pyproject.toml`, `uv.lock`.
- [x] Code: `ai/result`, `ai/run`, `ai/durable.py`, `ai/agents/context.py`, `ai/agents/agent.py`, `ai/tools`, and the export maps in `ai/__init__.py`, `ai/agents/__init__.py` and `ai/agents/pydantic_agent.py`.
- [x] mypy override for `pydantic_ai.run` in `pyproject.toml`.
- [x] Tests, knowledge base pages, the `config/constants.py` comment, `changelog.d/1446.md`.
