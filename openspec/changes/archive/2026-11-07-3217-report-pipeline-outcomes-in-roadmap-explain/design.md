# Design

## Decisions

- **Build the totals from the trace of the last implement run, and add no run history.**: The job record already holds the trace, and `src/devops_cli/roadmap/implement/implement_trace.py:def model_call` and `src/devops_cli/roadmap/implement/implement_trace.py:def attempt` hold every value that the report needs.
- **Count a repair round as an attempt event whose `next` is `repair`.**: The attempt event marks each repair round of a step, and the record already holds the trace.
- **Count an outcome as the `outcome` field of an attempt event, `passed` or `failed`.**: The attempt event names the outcome of a step, and a check event is one command, not the outcome of a step.
- **Give the totals in the text report and as a JSON object under `--json`.**: A test compares exact values without parsing prose, and a person reads the text report of the command.
- **Fill the totals inside `explain_item`, from the issue that it already reads.**: The command makes no second read of GitHub, and the existing requirement that it writes nothing still holds.
- **Read the trace in the verdict report through the same decode as `--trace`, so a trace that is not JSON stops the command and names the key.**: One reader of the record gives one behavior, and a corrupt record is reported instead of shown as an item with no run.
- **Refuse `--json` together with `--trace` with a message that names both options.**: Each option prints a different report, and `_one_mode` would name a flag `--json-output`, so the refusal carries its own message.
- **Deliver no dashboard panel agreement test, and leave it to #3851.**: Open item #3851 holds that test and waits on this change, and the refine block of this issue states that the panels are totals by repository and class, so no panel value equals one item's value.
- **Depend on no other item.**: #3069 adds the metrics of the Service and no field that this report needs, and the trace of the last run holds the totals already.

## Rejected alternatives

- **Add a per-item run history first.**: The record holds the trace of the last run, which `src/devops_cli/roadmap/explain.py:def read_trace` reads, and the trace holds the outcome, the tokens and the seconds of each event, so no new store is needed.
- **Read a repair-round count that #3069 records.**: #3069 is open and adds no such field today, and `src/devops_cli/roadmap/implement/implement_trace.py:def attempt` marks each repair round with `next` `repair`.
- **Print the totals as text only.**: A test would parse prose and break on a wording change, and the exact values of the JSON object do not move with the wording.
- **Print JSON only.**: A person reads the text report of the command, and the three job lines are already text.
- **Count the `retry` events as repair rounds.**: `src/devops_cli/roadmap/implement/implement_trace.py:def retry` is also a send again of a model request, so it counts sends and not repair rounds.
- **Compare each dashboard panel value with the explain output in this change.**: Open item #3851 holds that test and states that it waits on #3217, and the refine block of this issue states that the panels are totals by repository and class, so no panel value equals one item's value.
