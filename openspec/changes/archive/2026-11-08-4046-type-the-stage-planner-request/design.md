# Design

## Decisions

- **One model holds the model fields and the gate fields.**: The issue asks for one `StageRequest`. A later change (#4064) keeps the request as a file and judges a plan again, so the gate inputs must live in the same object as the fields that the model reads.
- **`for_model()` is `model_dump(exclude=GATE_ONLY_FIELDS, exclude_none=True)`.**: The four optional keys (`rejected_plan`, `overlaps`, `metric_senders`, `probes`) default to `None`, so they are absent when empty, and the field order is the key order of today. A test with a fixed item compares the JSON text that the model gets.
- **The gate inputs have their own names.**: `overlap_pulls` (the `Overlap` objects) and `probe_lines` (the lines) do not clash with the model keys `overlaps` and `probes`. `issue_body` is the full body, because `body` is cut to the token limit and the criteria gate needs the whole text.
- **`gate_arguments(request, tree, *, known, ...)` returns a dictionary of keyword arguments.**: `check_proposal(proposal, **gate_arguments(...))` and `check_gates` use it. The arguments that depend on the commit or on the proposal (`requirements`, `requirement_texts`, `read_text`, `registry`, `constants`, `search_evidence`) are keyword inputs, so the function needs no planner.
- **The creators are read in `_request`.**: Putting them in the request makes the read happen before the model call. The reader is cached for the run and the gate always calls it, so the value is equal. A Blocked item already calls it before the model.

## Rejected alternatives

- **Pass the planner object to the gates, as today.**: A gate then cannot run from a kept plan. `_problems` reads `_probe_lines`, `_overlaps` and `_creators()` from `self`.
- **Use the same name `overlaps` for the model entries and the gate objects.**: The two forms differ (dictionaries and `Overlap` objects). One field cannot hold both, and the model would get the objects.
- **Build the model JSON by hand and keep the dictionary.**: This is the untyped request of the issue, with no check of keys. pydantic gives `extra="forbid"` for free.
- **Add a new library for the request model.**: pydantic already covers every need and the project uses it for every model.
