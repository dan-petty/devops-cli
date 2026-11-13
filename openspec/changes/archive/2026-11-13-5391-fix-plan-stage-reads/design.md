# Design

## Decisions

- **Judge only the sentences that a repair adds or changes.**: The trace gate of the run that wrote the head passed each Feasibility sentence of it: the step stops a branch with a commit of another author, and the stage job and the step push only a plan that passed the checks with the facts of its plan runs. So a sentence that a reply keeps word for word holds a claim that a run already proved. A sentence that the reply adds or changes is a new claim, and the reads of the repair must support it.
- **Compare whole sentences in the form that the gate reads.**: `feasibility_sentences` uses `_sentences`, the split and the white space rule of `_trace_problems`. A changed line number, path or word makes a new sentence, which the gate judges.
- **Keep the set on the planner and clear it with the item.**: `revise` sets `_judged` after `_start_item`, and `_start_item` clears it, so a stage run of the next item judges every sentence. `_gate_problems` gives it to `gate_arguments`, so `_settle` and its callers do not change.
- **Remove at most two line numbers after the path of a tool span.**: The stage `read_file` takes `start_line` and `end_line`, and the planner writes the call as `read_file path 50 215`. The rule applies only after a toolbox tool name, as the removal of the tool name does, so `cat path 50 215` stays whole and is refused.

## Rejected alternatives

- **Keep the trace facts of the stage run with the plan.**: The stage job writes the facts only to its plan file, and it deletes that file when it stages the item (`_stage`). A durable copy needs a new record key or a file in the change folder, and a file in the change folder goes into the merged plan. The sentences of the head are the record that already exists.
- **Give the repair all paths that the head cites as read.**: A sentence that cites a path without a read claim, such as "`x.py` has no field `load`", would then support a new read claim of `x.py` that no run made.
- **Tell the planner to read each refused path again.**: The gate returns already name the path. On #5390 the named path was not a file, and three returns cost 2.4M tokens with no progress. A reread costs tokens for each kept citation and proves nothing that the gate of the head did not prove.
