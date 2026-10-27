# Proposal

## Why

Issue #2370: `devops roadmap intake` refused a new candidate with "type '' is not one of type/feature, type/bug, …", two times in one run, and filed nothing.

- `ModelProposal.type` is `str = ""`. `GatewayIntakeModel.propose` sends the JSON schema of `ModelProposal` to the gateway as `response_format`, so the schema lets the model leave `type` out or empty, also when the candidate has no type label.
- `priority`, `value` and `effort` are free strings in the schema too, though each has a fixed list.
- Intake finds the bad value only after the reply. #1677 then asks the model again, and the second reply can be bad in the same way.

## What Changes

- `GatewayIntakeModel.propose` sends a reply schema made for the request. In it, `type` is required and is one of the request's `types`, `priority` is one of `P1-High`, `P2-Medium` and `P3-Low`, and `value` and `effort` are one of `High`, `Medium` and `Low`. The schema carries each list as an `enum`. A request with no `types` keeps `type` as free text.
- The structured output of the gateway keeps the reply to the enums. A reply that does not keep to them fails validation in `chat_structured`, which asks again with the validation errors, before intake reads it.
- `validate_proposal` is not changed: it checks the proposal of every `IntakeModel`.
- Intake asks the model once for each candidate. The second request of #1677, which sent the problems of an off-list proposal back as `problem`, is deleted: `chat_structured` already asks again with the validation errors when a reply breaks the schema, and with the enums an off-list value breaks the schema. A proposal that still has a value off its list skips its candidate with the problems in the report, as a second failed request did.
- The reply of the model is observable behavior of `devops roadmap intake`, so the change carries a spec delta: the new capability `roadmap-intake-reply-schema`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-intake-reply-schema`: the schema that intake sends for the model's proposal.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/intake_model.py`, `src/devops_cli/roadmap/intake.py`, `src/devops_cli/ai/tasks/roadmap_intake_system.md`.
- `tests/test_roadmap_intake.py` and its prompt snapshot.

## Feasibility

- `ModelProposal.model_json_schema()` at the base commit: `type` is `{"default": "", "type": "string"}`, `priority`, `value` and `effort` are `{"type": "string"}`, and `required` is `["priority", "value", "effort"]`. No field has an `enum`.
- `chat_structured` (`src/devops_cli/ai/client/structured.py`) sends `schema.model_json_schema()` as the reply constraint and validates the reply with the same class.
- LiteLLM `v1.103.0` sends the schema of a `json_schema` `response_format` to Ollama as `format` (`litellm/llms/ollama/chat/transformation.py`). Ollama makes a grammar from that schema, and the grammar keeps an `enum` field to its values.
- Pydantic renders a `Literal` field as an `enum` in the JSON schema and refuses any other value. `src/devops_cli/ai/mcp/generator.py` builds a `Literal` from a list of choices in the same way.

## Existing Tool Considered

Pydantic's `create_model` and `Literal` make the schema for each request, and the JSON Schema `enum` keyword with the structured output of the gateway keeps the reply to it. No code is built for the check. The issue asked whether intake can read the type from the Conventional Commit prefix of the title: the design records why it does not.

The change deletes `_retry_proposal` in `src/devops_cli/roadmap/intake.py`, the `problem` field of `ProposalRequest`, the sentence of the intake prompt that explains `problem`, and the tests of the second request.
