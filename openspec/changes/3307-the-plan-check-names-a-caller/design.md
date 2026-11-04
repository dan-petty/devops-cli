# Design

## Decisions

- **Add the caller check to `path_problems` in `stage_paths.py`.**: The issue names the path gates, and `check_proposal` already calls `path_problems`, so the job and the replay keep one rule set.
- **Read the function name from each task text of the form Add ... to `name`.**: The issue states this form, and the task of #3200 that added `probes` to `check_proposal` uses it.
- **Name every file under `src/` that the caller search returns.**: The issue says every caller, and `git grep` reads the same commit as the path gate.
- **Skip the check on a tree with no checkout, as the replay builds it.**: The replay reads no git, and a refusal would need a caller set that it cannot read.
- **Return one sentence for each missing caller file.**: A person can act on each file, and the model gets the exact path.

## Rejected alternatives

- **Add the check to `check_proposal` in `stage_change.py`.**: It would not sit with the path checks and would need a second tree walk.
- **Add a new gate in `stage_eval_gates.py`.**: The job must refuse the plan before a draft opens, and the replay reads no git.
- **Parse the `changes` list for the function name.**: The list holds paths, not the signature of a function.
- **Ask the model to declare the callers.**: The check must be deterministic and offline.
- **Require only the callers that pass the new parameter.**: The issue says every caller, and a default parameter still leaves the call to review.
- **Parse every file with an AST.**: The project has no AST index, and the issue asks for a textual search.
- **Fail the replay when it has no checkout.**: It would break every case with no source.
