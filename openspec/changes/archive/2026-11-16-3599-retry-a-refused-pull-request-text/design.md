# Design

## Decisions

- **Refuse a body whose text ends with `...` or `…` in `_text_problems` of `src/devops_cli/roadmap/pull_form.py`.**: The form check refused a cut summary but not a cut body, so a why that ends with `...` reached the pull request. One rule in the shared helper covers the delivery body and the plan body, and `build_body` raises with every problem instead of writing the text.
- **Judge only the end of the text for a cut mark, and not a `...` inside a sentence.**: A text such as `Closes #1 ... and more` is no cut, and a rule over every `...` would refuse a right body.
- **Put the one retry in a new module `src/devops_cli/roadmap/pull_retry.py`.**: `pull_form.py` reads no file and makes no request by design, so the model call sits beside the form rules and not inside them, and one copy of the loop keeps the retry in one place.
- **Change no stage code.**: This run read no line of the stage job's plan-body path, so the plan covers the implement job and leaves the stage job's own path to its own item.
- **Add `refused_reply` to `FailureClass` with the action `WAIT`, in the same group as the row of `docs/ROADMAP_WORKFLOW.md`.**: The taxonomy of twenty classes names no reply that fails its checks twice; `WAIT` says that a person edits the text or the proposal and comments `implement: retry`, because the model has had its one retry. The document and the enum move together, so no reader sees a class with no row.
- **Make one model call and no third call for the body.**: One retry bounds the cost of a step, and a loop over refusals grows without a limit.
- **Send the refused text and every problem of the form check to the model.**: The model edits the text and keeps the facts that the job already read; the problems alone would make it rebuild the text from the sources and lose a fact.
- **Take the model call as the keyword `rewriter`, as the job takes `splitter`.**: The tests pass a fake and reach no network, and the command builds the real client, as it already does for the splitter.
- **Judge the rebuilt body with `build_body` again.**: The same rule judges the first text and the rebuilt one, so no placeholder and no `...` reaches the pull request.
- **Keep the seven scenario names of the base requirement in the `modified` entry, and give `A refused body stops the item` the text of a second refusal.**: OpenSpec replaces the whole requirement, so every name a test or a reader knows stays; the new text states the stop that follows the one retry.
- **Add the retry as a new requirement `A refused body is rebuilt once` and keep the base text of `The job rewrites the pull request after the push` word for word.**: A requirement text holds at most 500 characters. The base text is 487, so the retry rule does not fit beside it; the new requirement states the retry and its three scenarios, and the modified requirement only gives its refused-body scenario the second refusal.

## Rejected alternatives

- **A retry loop inside `src/devops_cli/roadmap/pull_form.py`.**: The module reads no file and makes no request by design, as its docstring states, and a model call would break that.
- **A retry loop in each job.**: Two copies drift, and the two jobs can stop on different rules for the same cause.
- **Re-run the whole implement step when the body is refused.**: The step repeats the work of the group and exceeds the budget of one step.
- **A retry on every refusal.**: The model calls grow without a limit, and the cost of a step is unbounded.
- **Cut the text so that it fits the 1,000 characters of the body.**: `build_body` raises `ValidationError` that names the limit and cuts nothing, and after this change `_text_problems` refuses a text that ends with `...`, so a cut text is refused twice over.
- **Build the retry on `pydantic-ai-slim`.**: The alternatives check of 2026-11-07 gives it as partly: it retries a structured reply that breaks its schema, which `chat_structured` already does, and it knows nothing of `build_body` or `plan_body_problems`.
- **Put the shared function in `src/devops_cli/roadmap/messages.py`.**: The probe reports that the path is no file of the staging commit; the messages of the project live in `src/devops_cli/lang/en/messages.py`.
- **Drop the base scenario `A refused body stops the item` and write a new scenario name for the second refusal.**: A `modified` requirement holds all of its scenarios, so the name stays and its text states the stop after the one retry.
- **Put the retry text into the modified requirement `The job rewrites the pull request after the push`.**: That text is already 487 characters, and a requirement text holds at most 500, so the retry rule goes into the added requirement `A refused body is rebuilt once`.
