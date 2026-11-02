# Design

## Decisions

- **The pass lives in the planner.** `_Planner.plan` already owns the returns of a reply (the gates and the split). After `_settle` gives a `StagedChange`, `plan` calls the pass. A return for a finding uses the same request with `previous` and `problem`. `StagedChange` keeps the `StageProposal` and the findings, so `_stage_one` and the comment need no second source.
- **One return, then advice.** A finding of type `missing_path`, `false_premise` or `ignores_existing_code` with a quote that is in the input returns the plan once. The revised plan passes the gates and the verification again. Its findings, whatever the type, go into the comment and the draft opens. This keeps the model from holding a merge gate: the issue says the pass is advisory beyond the one return. A revised plan that fails the gates stops the item with the message of the gates, as a second refused reply does today.
- **A quote counts only when it is in the input.** The pass checks that the quote of a finding is a substring of the request text (white space folded). A model that invents a quote cannot return a plan. The finding still goes into the comment. This is the whole meaning of "quotes evidence": no judge call, and a test can assert it.
- **The nine types are the enum of the golden set.** `Finding.type` is `DefectType` from `stage_eval_cases.py`. A pydantic enum refuses an unknown type, and `chat_structured` returns the reply once. A second bad reply raises `StructuredOutputValidationError`, which skips the item, so no draft opens. The prompt and the schema name the same nine types, and a test compares them.
- **The plan is the JSON of the proposal.** The job passes `StageProposal.model_dump(mode="json")`, and the eval passes the raw `plan.json` of the case, which has the same shape. The golden set keeps plans that fail the schema, so the eval cannot rebuild a `StageProposal` for each case.
- **Cited files.** A plan cites the paths of `reads` and `changes` of each group. The pass reads the ones that are files of the checkout, in plan order, each cut to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens with `truncate_to_token_limit`, up to `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files. A path that is not a file inside the checkout is left out: the gates judge a missing path.
- **The slot, not a model name.** The caller builds `get_llm_client(task="verification")`. The code names no model. A person sets the model in `ai.tasks.verification`, and the gateway holds the fallback (#3154).
- **The caller passes the verifier.** `plan_stage(verifier=...)` keeps the tests that use `model=` unchanged, and the golden-set run of the planner makes no verification call. The two production callers pass it. A test of each caller shows the call.
- **A failed verification call skips the item.** Like a failed planner call, a failed verification call raises `AIClientError` and the item waits for the next round. A draft that no check judged would be worse than a delay. Rejected credentials stop the run.
- **Findings go into the comment of the job.** The job posts one comment on the issue, with the marker, that names the draft pull request. The findings are a section of that comment, with the type, the place, the problem and the quote, each cleaned with `safe_text` so a handle or a link pings no one. The job adds no second comment and makes no call to the pull request. Rejected: a comment on the pull request itself. It is a second write for each item, and the person who reviews the plan reads the comment of the job.
- **The eval matches one finding to one defect.** A finding of a type matches at most one labeled defect of that type, taken in the order blocker, major, minor, nit. The recall is matched defects over labeled defects. A type-only match would let one finding of type `other` cover all 98 `other` defects. The match is by type and not by text, so a finding of the right type on the wrong spot counts. The text of each finding is in the stored JSON for a person to read.
- **pydantic-evals runs the eval.** A `Dataset` of the cases, a task that runs the pass on one case, and an `Evaluator` that scores the case. The totals are plain code over the report, so a test checks them without the library.
- **The eval reads files from git.** The set stores the plans and not the files, so the eval uses `checkout_at(source, case.base_commit)` as `eval stage` does. `--source` names the repository.

## Rejected alternatives

- **Loop until clean.** It can spend many calls and delay the item without a person. The issue limits the pass to one return.
- **No return.** The most serious findings would stay in a comment, and a person would merge the plan with a false premise.
- **Block the draft on every finding.** It gives a model finding a merge gate that the project does not give it.
- **A new `stage_verification` slot.** It duplicates a slot that already exists.
- **A hard-coded model.** A model change would need a code change.
- **Extend `roadmap eval stage`.** It would mix the quality of the plan with the quality of the verification in one score, and the verifier needs the cited files, which the stage run does not read.
- **A second judge call for the quote.** One more call for each finding, and a test cannot assert it offline. The substring check costs nothing.
- **Verify the rendered files in place of the JSON.** The golden set holds plans that do not render, so the eval and the job would send two forms.
