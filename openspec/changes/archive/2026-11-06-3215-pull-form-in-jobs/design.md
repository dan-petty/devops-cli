# Design

## Decisions

- **`build_plan_body` lives in `pull_form`.**: It mirrors `build_body`, takes the plan rules from `plan_body_problems`, and raises `ValidationError`. The rules for `Plans #` stay in one module.
- **The implement "why" is the archived Why or the issue title, and is never cut.**: The Why must fit in `BODY_MAX_CHARS` less the length of the `Closes` and `Change:` lines, because the limit counts all three. A Why that does not fit, is empty, or holds a closing keyword for an issue gives way to the title of the issue. The refusal of `build_body` covers every other problem.
- **A refused implement body stops the item.**: The step name is `pull request`, as for a refused title, and the job pushes nothing more. The branch and the draft pull request already exist, so no work is lost.
- **The stage job returns a refused plan body to the model once.**: The body is the model's `pull_request_body` field. A refused field joins the problems of the plan check, and the existing one return and the existing stop on a second refusal apply. The check for a closing keyword runs first and keeps its own stop.
- **The attribution lines stay out.** The implement job writes none today, so it passes no `attribution`.

## Rejected alternatives

- **Relax `body_problems` to accept `Plans`.**: The delivery form must keep refusing a body with no `Closes`.
- **A model-written summary field for the implement "why".**: It repeats the Why of the plan, and needs a prompt, a schema and tests.
- **A model retry of the implement body now.**: The job has no free-text step for it. Issue #3599 holds the retry.
- **Keep `textwrap.shorten`.**: It writes `...`, which the form refuses as a cut text.
- **Wait for the content gate (#3200).**: The jobs need none of it, and the edits are small.
