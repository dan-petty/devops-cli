# Design

## Decisions

- **Every chat slot names `deepseek-v4.1-flash-1017`.** The owner decision of 2026-11-07 is one model for all model configs until most steps work most of the time. `analysis` and `implement` already name it, so the change sets `ai.model`, `verification`, `chat` and `triage`.
- **The embedding slot stays `qwen3-embedding:0.6b`.** A chat model cannot embed, and an embedding stays in the cluster.
- **The test resolves tasks with `for_task`.** A task that the template leaves unset takes `ai.model` or its parent, so a new task is covered without a change to the test.
- **`ai.max_retries` stays 1, with a new reason.** The gateway retries a failed call of the group up to 5 times, and OpenRouter bills the calls. A removal of the client retry or a higher value needs a measure of hosted failures, which does not exist. A person can decide it after the Service runs on the group.
- **The comment in the template is the record of the decision and of its end.** The condition to undo it is "when most steps of the roadmap jobs work most of the time".

## Rejected alternatives

- **Keep `verification` on `claude-sonnet-5-5`.** The owner asked for one model, and no code reads the slot before #3153.
- **Move the local aliases to a fallback.** The gateway fallbacks decide this, not the client config, and SECURITY.md rule 13 forbids a fallback from a non-hosted group to a hosted group.
- **Change `max_retries`.** The issue does not ask for it, and no measure of hosted failures supports another value.
