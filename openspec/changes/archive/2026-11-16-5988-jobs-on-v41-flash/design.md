# Design

## Decisions
- Change the models in the template only; the gateway groups stay as they are, so a return to -1017 is a template change.
- Keep `context_window` 256000 for each task: each fp8 endpoint of the new model allows 1,000,000 tokens or more.

## Rejected alternatives
- Point the gateway alias of -1017 at the group `deepseek-v4.1-flash`: the settings would name a model that the gateway does not call, and the spend records would not match the settings.
- `provider.sort: "latency"` on the -1017 group: not tested, and the price can be higher.
