# Design

## Decision

`chat_structured` is the one structured-output path. The agent loop's schema arm, the pipeline's second parse and the duplicate reflection builder are deleted, because no production code reaches them.

## Rejected alternatives

- **One new module that both `chat_structured` and the agent loop call**, as the issue planned. Rejected: the agent loop's arm has no production caller (`rg -n "output_type=|output_schema=|output_validator\(" src` finds none outside `ai/agents/`), so the module would keep a second caller alive for tests only. The owner's direction (#1001, #1419, #1005) moves structured output to pydantic-ai, which would delete the module again.
- **Run the agent loop's validation on pydantic-ai's output processors.** Rejected: they live in the private `pydantic_ai._output` module, and only a native `Agent` runs them. Adopting the native agent is #1005.
- **Keep `MultiAgentPipeline.output_schema` and report a failed parse in the stage result**, as the issue's criterion asked. Rejected: no production pipeline sets a schema, so the report would have no reader.
- **Keep `AgentResponse.data`.** Kept: the deferred-tool path returns its `DeferredToolRequests` there. Only the schema arm stopped writing it.
