# Design

## Decisions

- **The path rule lives in `check_proposal` and reads the `changes` paths of every group.**: `check_proposal` already holds the rules that a schema cannot say, and the job (`_settle` of `stage.py`) and the replay (`_path_gate` of `stage_eval_gates.py`) both call it.
- **A path counts as a non-spec path when it starts with `tests/`, `.github/workflows/`, `docs/` or `openspec/`.**: The issue names these four prefixes, and they cover the test, CI, document and plan changes that need no spec delta.
- **The duplicate check compares the ADDED requirement name with the requirement names of the base spec of that capability.**: The base spec is the living specification, so an ADDED requirement with a name that is already there is a no-op or an error. A MODIFIED requirement keeps its name, so only ADDED is checked. `check_proposal` takes the names as the keyword `requirements`, a map from capability to names, so a caller that has no base spec passes none.
- **The model input holds the purpose and the requirement names of each capability.**: The model cannot choose the right capability or avoid a duplicate from a bare name, and the issue asks for both. A new module `stage_specs.py` reads the Purpose section and the `### Requirement:` headings of each `openspec/specs/<capability>/spec.md`, and `capabilities` in the request becomes a list of `{name, purpose, requirements}`.
- **The replay of #2977 sets the `paths` gate on its spec-delta defect.**: The recorded case of #2977 (the case folder `2116-...`) holds the defect as `spec_delta_wrong` with the gate `pending`. The defect type keeps waiting for a gate for its other forms (a wrong capability), so the type stays in `PENDING_GATES`, and the case names the gate `paths` and the message that the new problem holds. A recorded case holds no requirement names, so the replay of a case judges the path rule only; a live run of the replay passes the names of the checkout.
- **The problem text goes back through the existing retry of `chat_structured` and the `stage_invalid` error.**: The job already sends a problem back once and stops the item on a second failure, so the change adds no loop and no error class.

## Rejected alternatives

- **Refuse a spec delta from the title type of the issue instead of the changed paths.**: The issue names the `changes` paths, and a plan of a `fix` can still change only tests. The paths are what the plan itself states.
- **Compare the full text of an ADDED requirement with the base spec.**: A MODIFIED requirement keeps its name and changes its text, so a text comparison would refuse a good plan. Only the name marks a duplicate.
- **Add a second retry loop for the new rules.**: `chat_structured` already sends a schema violation back, and `check_proposal` problems already go back once through the existing retry (`_settle` of `stage.py`).
