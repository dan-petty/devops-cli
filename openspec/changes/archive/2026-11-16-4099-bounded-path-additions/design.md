# Design

## Decisions

### Dedicated `_judge_add_path` function
`_judge_path` replaces a code span for a rename, whereas `_judge_add_path` appends a new path to a named header line (`Changes:` or `Reads:`). Keeping them in separate functions keeps the rename checks clean and avoids mixing two distinct amendment rules.

### Explicit `header` field in `PlanRequest`
The request must explicitly specify `header: "Changes"` or `header: "Reads"`. The agent knows whether it reads or modifies the file, keeping the write set minimal. If `header` is omitted, the request is refused.

### Reusing refusal message `implement_amend_refused_path_status`
The refusal for absent paths, paths under `openspec/`, duplicate paths, or missing header lines reuses `implement_amend_refused_path_status`. This avoids unnecessary localization changes while accurately conveying that the path status does not meet amendment criteria.

## Rejected alternatives

### Always appending to `Changes:`
Rejected because appending read-only files (e.g. fixtures, constants) to `Changes:` needlessly widens the modified-file bounds of the step.

### Automatically inferring the header line
Rejected because groups often contain both `Reads:` and `Changes:`, so an agent-supplied path cannot be deterministically inferred as a read vs. write without an explicit field.
