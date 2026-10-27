# Design

## Decisions

- **One schema for each request.** `proposal_schema(types)` returns a subclass of `ModelProposal` made with `pydantic.create_model`, in which `type`, `priority`, `value` and `effort` are `Literal` fields with no default. The class is a `ModelProposal`, so intake reads the reply as before.
- **`type` is always required when the request has types.** A candidate that has a type label keeps it, and intake ignores the type of the reply (`needs_type`). To ask for a valid type in every request costs a few reply tokens and keeps the schema the same for each candidate, so `propose` needs no second flag.
- **The priority list is `CONST_ROADMAP_MODEL_PRIORITIES`.** The prompt tells the model to choose `P1-High`, `P2-Medium` or `P3-Low`, and only a person or verified evidence sets P0. The P0 cap in `validate_proposal` stays for other `IntakeModel`s.
- **One retry layer.** `chat_structured` validates each reply against the schema of its request and asks again with the validation errors. With the enums, a value off its list is a validation error there, so the second request of intake (#1677) can no longer run for the gateway model. It is deleted with the `problem` field that carried its feedback. `validate_proposal` still checks every proposal, and a proposal off its list skips its candidate.

## Rejected alternatives

- **Read the type from the Conventional Commit prefix of the title.** Only some candidates have a prefix, and a prefix does not always give one label: `fix` can be `type/bug` or `type/security`. The prompt already gives the model the prefix mappings, and the enum keeps its answer on the list.
- **Check the values after the reply only.** This is what failed: intake found the empty `type` after the reply, and the second request (#1677) failed in the same way.
- **Keep the second request of intake.** No reply of the gateway model can reach it, because `chat_structured` refuses an off-list value first. It would be a second retry layer for one fault.
- **A `StrEnum` for each list.** Pydantic writes an enum class into `$defs` and refers to it with `$ref`. A `Literal` writes the `enum` into the field, which is the smaller schema for the grammar.
