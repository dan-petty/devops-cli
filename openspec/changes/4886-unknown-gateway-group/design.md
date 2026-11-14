# Design

## Context

`_is_local_tier` holds only the four virtual models. The gateway config has more local groups, and a fallback names the deployment model.

## Goals

- One constant for the local groups.
- A local fallback is local, and a hosted group stays hosted.

## Decisions

- **The config is the source.** The test compares the constant with the deployments whose model starts with `ollama/` or `ollama_chat/`.
- **The prefixes.** A reply that names `ollama_chat/qwen3.8:27b` or the bare group is local.

## Risks

- A new local group in the config without the constant fails the test. That is the change a person should see.

## Tests

- The constant equals the local groups of the config.
- Each local group and the prefixed model is local.
- A hosted group is not.
