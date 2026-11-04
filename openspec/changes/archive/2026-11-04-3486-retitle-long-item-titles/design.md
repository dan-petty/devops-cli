# Design

## Context

`pull_form.py` holds the title rule, and it never cuts a text, because a cut text ends with `...` and the form check refuses it. The roadmap jobs read titles through the roadmap store. The stage job bounds the summary of a plan title.

## Decisions

- **Separate command `retitle`.** It repairs titles without waiting for the stage or the implement job. The stage job sees Ready items only, and the implement job reaches the title check after it spends tokens.
- **Plan pull request title for a Planned item.** `STAGE_SUMMARY_MAX_CHARS` bounds it, so the job needs no model call.
- **One model call, one retry, for an item with no plan.** The reply must pass `build_title`, which calls `title_problems`. Two faulty replies leave the item.
- **A person's edit is found on the timeline.** The job compares the newest `RenamedTitleEvent` with the newest comment that holds a job marker. A rename with no job comment counts as a person's. The job writes the title before its comment, so its own rename never looks like a person's.
- **Intake refuses in the command.** `intake_candidate` serves the review hand-off, which files titles of up to 200 characters. A refusal in `plan_intake` would stop that hand-off, so the refusal is in `devops roadmap intake --title`.
- **A skip comments only for a Planned item without a usable plan title.** The comment text is the same on each run, so the job posts it once.

## Rejected Alternatives

- **Adopt `amannn/action-semantic-pull-request`.** It checks a title in CI and cannot rewrite an issue title.
- **Cut the title at 60 characters.** A cut ends mid-word, ends with `...`, and can break the type or the scope. `pull_form.py` refuses it.
- **Add the repair to the stage job or the implement job.** The stage job leaves out Planned items, and the implement job has already spent its tokens.
- **Model call for a Planned item.** It costs tokens and can change a summary that already exists.
- **Refuse in `plan_intake`.** It breaks the review hand-off (see Decisions).
