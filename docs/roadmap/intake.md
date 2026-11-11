# The intake job

`devops roadmap intake` turns candidates into items. It is step 1 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What a candidate is

A candidate is one of two things:

- An open issue that has no `priority/*` label. Intake takes every such issue, or only the issues named with `--issue`.
- A new issue that does not exist yet. A caller files it with `--title` and `--body-file`. Intake labels the new issue `source/agent` when an agent files it, which is the default of `--filed-by`. A person who passes `--filed-by person` gets no such label.

A text that looks like it holds a secret is refused.

A new candidate whose title has a Conventional Commit type and a summary of more than 60 characters is refused with `--title`. An emoji counts as two. The message names the length and the limit, and intake files no issue. The stage job and the implement job leave out an item with such a title, so the filer writes a shorter summary. `devops roadmap retitle` shortens the title of an open item that already has a long summary (see [the retitle job](#the-retitle-job)).

## What intake writes

For each candidate, intake sets these fields on GitHub:

1. A `type/*` label and a `scope/*` label, from the Conventional Commit title. The model picks the type only for a title that has no Conventional Commit type.
2. The label `status/new`.
3. A Value label and an Effort label.
4. A reason comment.
5. The `priority/*` label, last. The item then goes to the backlog.

A label that a person set stays. Intake sets no milestone, because a person plans the milestones. A milestone that an issue has stays.

## Duplicates

The model compares each candidate with the items and with the issues that a person closed as not planned. It does not compare a candidate with an issue that has sub-issues, because the sub-issues deliver that issue.

The model can name a possible duplicate. Intake then places the candidate as usual, and the report and the reason comment name the possible original for a person to close. Intake never closes an issue and never drops a candidate. This holds for a new candidate too: intake files it even when it is a possible duplicate.

A run can stop after it filed a new candidate. The next run finds the open issue that has the same title and body, and places that issue. It files no second issue.

To keep an issue off the roadmap, close it as not planned:

```text
devops gh issues close <number> --reason not-planned
```

## Jev for the proposal

The setting `roadmap.intake.jev` has three values (ADR 0019). `off` is the default and makes no Jev request. `shadow` keeps the `triage` model for every label and every flag, and records what TypeSafe Jev (`typesafe/jev-1.14`) would answer. `on` asks Jev for the fields of the proposal in place of the `triage` model. Jev must not decide yet: on the 25 closed issues of `devops roadmap eval jev` it ties the `triage` model on type, and it is behind on priority, Value and Effort. Use `shadow` to measure it on real new issues.

One request holds a question for each field that has a fixed list:

| Field | Question | Answer |
| :--- | :--- | :--- |
| Type | Pick one of the `type/*` labels of `.github/labels.yml`. Asked only when the title and the issue give no type. | The label |
| Priority | Pick one of `P1-High`, `P2-Medium` and `P3-Low`. | The priority |
| Value, Effort | Score a rubric of three levels. | The level, rounded |
| Duplicate | One yes/no question for each nearest item. | A possible original, when the probability reaches 0.90 |

### Mode `on`

Jev writes no text, so the reason lines say which option Jev chose and how sure it was. Jev gives no evidence for a P0 and no related item. The proposal goes to the same checks as the proposal of the `triage` model, so the checks decide which values stand, and a flagged duplicate only flags: the candidate is still placed.

Intake uses the `triage` model for the whole proposal when a Jev request fails, times out after 30 seconds, or gives a choice or score with a confidence below 0.60. The counter `devops_cli_roadmap_intake_jev_fields_total` shows, for each field, how often Jev (`jev`) or the fallback (`fallback`) gave it.

Do not set `on` before `devops roadmap eval jev` shows that Jev flags no more false duplicates than the `triage` model, and before the shadow report supports it. The command runs both models on the duplicate cases and on 25 closed issues with the labels a person set, and stops before its first call when it needs more calls than `--max-calls`. With `--min-confidence`, it counts a Jev answer below that confidence as no answer, as intake does at 0.60; the default 0 takes every answer to measure what Jev knows.

### Mode `shadow`

After the `triage` model answers and the checks of intake accept the reply, intake asks Jev the same questions, one request for each candidate (about 0.0001 USD). The text of the title and the issue goes to the hosted model, as in any model call of intake, and intake refuses a candidate that holds a secret before it. Jev changes nothing: no label, no flag and no comment come from it. A Jev error or timeout changes nothing too. It only counts.

Intake records the observation in the job record of the issue, as the mark `intake.jev_shadow`, in the same write as the Priority. The mark is compact JSON that holds the time of the proposal and, for each field, three values: the Jev answer, its probability, and the `triage` answer. For the duplicate, the Jev answer is the nearest item that reaches 0.90 (or empty), the probability is the highest one of any nearest item, and the `triage` answer is the possible original that intake took (or empty). The mark holds no text of the issue. A candidate that Jev could not answer has no mark.

Shadow counts in the same counter as mode `on`, `devops_cli_roadmap_intake_jev_fields_total`, with its own values of the label `outcome`: `agree`, `differ` and `jev_error`. The label `field` is type, priority, value, effort or duplicate. Mode `shadow` writes at most 15 series for each pod, mode `on` at most 10, and the counter has at most 25.

To read the records, run:

```text
devops roadmap eval jev --from-shadow
```

The command reads every issue of the repository (GitHub reads, no model request, no write). For each field it prints how often Jev and the `triage` model agree, how often each equals the label the issue holds now, how often only one of them does, and how often Jev is right in each band of its probability (below 60%, 60 to 75%, 75 to 90%, 90% and above). For the duplicate it counts the flags of each model against the issues that GitHub shows closed as a duplicate. The final label is a weak truth: intake writes the `triage` label, and a label that no person changed counts as final. Read the columns "only Jev" and "only triage" first.

## The issue listing

Intake compares each candidate with every item and with every issue closed as not planned, so each run needs every issue of the repository. `devops roadmap intake` keeps a snapshot of the issue listing in `roadmap/listing/<owner>/<name>.json` under the data directory. The snapshot holds the parsed record of each issue and pull request, the version of devops-cli that wrote it, the time of its last full read and a watermark.

- A run reads only the issues and pull requests that changed since the watermark: `state=all`, `sort=updated`, `direction=desc` and `since=<watermark>`. Each changed issue replaces its record, so intake parses only the bodies of the changed issues. When 100 or fewer issues changed, the read is one request.
- The new watermark is the earlier of the start of the read and the newest `updated_at` that GitHub gave, less 60 seconds. Thus a local clock ahead of GitHub's clock skips no change.
- GitHub does not move the `updated_at` of a parent when a sub-issue joins or leaves it. A changed issue that joined or left a parent moves the sub-issue count of that parent by one.
- A run reads the whole listing and writes a new snapshot when no snapshot is kept, when the snapshot cannot be read, when another version wrote it, when its last full read is 24 hours old or older, and on `--full`. The full read removes an issue that left the repository.
- The snapshot is a copy of GitHub, which stays the source of truth. A snapshot that intake cannot read or write gives a warning. A failed write keeps the earlier file, because intake writes a temporary file and renames it.

The Service does not use the snapshot: its poll reads the whole listing. `SnapshotStore` in `src/devops_cli/roadmap/stores/listing_snapshot.py` is the seam for a store that the Service can share.

## A failed write

A write of GitHub can fail for one candidate, for example with a status 502. Intake skips that candidate, places the others, and then the run fails and names it.

The Service keeps the failure in its intake record, beside `schedule.json`, and not in the job record of the issue. The issue is a candidate, not an item, so it gets no mark. The record holds the step (`place`), the failure class (`ci_infra` for an error of GitHub), the count of failures in a row and the time of the last one. The next rounds leave the candidate out until the wait of the class has passed (`RETRY_AFTER` in `roadmap/failure.py`: 1 hour for `ci_infra`). They make no triage call and no embedding call for it, and the candidate does not make intake due. After the wait, intake decides the candidate again. A candidate that is placed, closed or no candidate any more loses its entry. A change that a person made to the Item while the job worked is no failure and leaves no entry. A webhook update of the issue keeps the wait, and `devops roadmap intake` keeps no record, so it waits for nothing.

## The three modes

| Flag | What the run does |
| :--- | :--- |
| `--dry-run` | Makes no request to GitHub or to a model. It prints the requests that a run makes. |
| `--plan` (the default) | Reads GitHub and calls the model. It writes nothing. It prints each planned change and what the run spent. |
| `--confirm` | Plans as `--plan` does, then makes the writes. |

## The retitle job

`devops roadmap retitle` shortens the title summary of open items that has more than 60 characters. The stage job and the implement job leave out such an item, and the check `Semantic PR title` refuses its delivery title.

- It takes the open items with a Conventional Commit type, the lowest number first, at most `--limit` (25) in a run. `--item` names one item.
- It keeps the type and the scope and writes only the summary. The new title passes `title_problems` of `src/devops_cli/roadmap/pull_form.py`.
- A Planned item takes the summary of the title of its plan pull request (`plan #<issue> <summary>`), which its job record names. The job makes no model call for it. When that title gives no valid summary, the job leaves the item and comments the reason once.
- Another item gets one request to the `triage` model, and one more with the faults of the first reply. A reply that fails twice leaves the item.
- It leaves a title that someone changed after the last comment of a job. It reads the title changes on the timeline of the item.
- When it leaves an item, it writes the mark `retitle.skipped` once. The value is a hash of the title, the body and the `stage.pr` mark. The selection leaves the item out while the hash holds, so a later round reads nothing of it and makes no model request for it. A change to the title, the body or `stage.pr` selects it again. A comment does not.
- Without `--confirm` it prints the new titles and writes nothing. With `--confirm` it writes each title and one comment with the marker `<!-- devops roadmap retitle -->`. `--dry-run` makes no request.
- The Service runs the job as the row `retitle` of the model lane. The row is due on a first run and every 61 minutes. It runs after `refine` and before `stage`, so the stage job reads the new titles in the same round. Each run takes at most 25 items and writes as `--confirm` does. The row needs no clone.

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| Duplicate verdict, report lines, no close, retry of a stopped run, the source of a part | [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
| Type and scope labels from the title | [roadmap-intake-title-labels](../../openspec/specs/roadmap-intake-title-labels/spec.md) |
| The reply of the model | [roadmap-intake-reply-schema](../../openspec/specs/roadmap-intake-reply-schema/spec.md) |
| The snapshot of the issue listing and the read of the changed issues | [roadmap-intake-listing](../../openspec/specs/roadmap-intake-listing/spec.md) |
| Intake of one issue on an `issues` event of GitHub | [roadmap-scoped-updates](../../openspec/specs/roadmap-scoped-updates/spec.md) |
| Jev for the proposal fields, and the comparison with the `triage` model | [roadmap-intake-jev](../../openspec/specs/roadmap-intake-jev/spec.md) |
| The evaluation of the duplicate verdict | `devops roadmap eval intake`, in [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
