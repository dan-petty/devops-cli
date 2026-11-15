# Design: #4081

## Context

`check_proposal` joins the problems of every gate for the stage job. The eval replay gives each
rule its own gate and judges a defect against the gate that names it. `_path_gate` reused
`check_proposal` to catch `missing_path`, `spec_delta_wrong` and `verify_form`, so the criteria,
content, citation and registry problems appeared under `paths` too.

## Decisions

- `_path_gate` calls `check_gates`, the function that returns the problems by gate, and joins all
  gates but `criteria`. The content rule stays in `paths`, as the module docstring records, and
  the other rules keep their coupling for now, since a later change can narrow each one.
- The criteria rule reads `plan.issue_body`, which is empty in a recorded case without a body.
  The paths gate no longer sees its problems, so a rule that refuses an unknown criterion cannot
  fail a valid plan through `paths`.
- A regression test holds both ways a criterion problem arises: a criterion left out and a
  criterion that names a group above the group count.

## Risks

- A defect of type `missing_path` that only a criteria message would explain no longer matches.
  No case of the golden set holds one: the replay over the set passes with `paths` empty for the
  two plans the regression test builds.
