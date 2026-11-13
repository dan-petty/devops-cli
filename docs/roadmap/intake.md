# The intake job

`devops roadmap intake` turns candidates into items. It is step 1 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What a candidate is

A candidate is one of two things:

- An open issue that has no `priority/*` label. Intake takes every such issue, or only the issues named with `--issue`.
- A new issue that does not exist yet. A caller files it with `--title` and `--body-file`. Intake labels the new issue `source/agent` when an agent files it, which is the default of `--filed-by`. A person who passes `--filed-by person` gets no such label.

A text that looks like it holds a secret is refused.

A new candidate whose title has a Conventional Commit type and a summary of more than 60 characters is refused with `--title`. An emoji counts as two. The message names the length and the limit, and intake files no issue. The stage job and the implement job leave out an item with such a title, so the filer writes a shorter summary. `devops roadmap retitle` shortens the title of an open item that already has a long summary (see [the retitle job](#the-retitle-job)).

Intake does not refuse a title whose type the branch types do not list, such as `security(ssh): ...`, also with a long summary. `devops roadmap retitle` corrects the type of the new item, and refine does not set the item Ready while the type is not listed.

## What intake writes

For each candidate, intake sets these fields on GitHub:

1. A `type/*` label and a `scope/*` label, from the Conventional Commit title. The model picks the type only for a title that has no Conventional Commit type.
2. The label `status/new`.
3. A Value label and an Effort label.
4. A reason comment, only when the labels do not show a fact: a scope that `.github/labels.yml` does not declare, the reason of a Priority other than P2-Medium or of a P0 decision on evidence, the possible original and the related item. The comment does not state the labels again.
5. The `priority/*` label, last. The item then goes to the backlog.

A label that a person set stays. Intake sets no milestone, because a person plans the milestones. A milestone that an issue has stays.

## Duplicates

The model compares each candidate with the items and with the issues that a person closed as not planned. It does not compare a candidate with an issue that has sub-issues, because the sub-issues deliver that issue.

To find the nearest items, intake embeds each item and each candidate. The embedder looks for each vector in the memory of the process, then in Valkey, then in the file `ai/embeddings.db` under the data directory. Only the texts that no cache holds go to the embedding model. The file keeps the vectors between two runs, so a run sends only the texts that changed since an earlier run. Its key is the provider, the model name that the request sends and the SHA-256 of the text, so a changed text, another model or another provider is a miss. A stored vector with a length that differs from the length of the model is a miss too. The file is a cache only: you can delete it at any time. A run removes each vector that no run used for 30 days.

The model can name a possible duplicate. Intake then places the candidate as usual, and the report and the reason comment name the possible original for a person to close. Intake never closes an issue and never drops a candidate. This holds for a new candidate too: intake files it even when it is a possible duplicate.

A run can stop after it filed a new candidate. The next run finds the open issue that has the same title and body, and places that issue. It files no second issue.

To keep an issue off the roadmap, close it as not planned:

```text
devops gh issue close <number> --reason not-planned
```

## Jev for the proposal

The setting `roadmap.intake.jev` has three values (ADR 0019). `off` is the default and makes no Jev request. `shadow` keeps the `triage` model for every label and every flag, and records what TypeSafe Jev (`typesafe/jev-1.14`) would answer. `on` asks Jev for the fields of the proposal in place of the `triage` model. Jev must not decide yet: on the 25 closed issues of `devops roadmap eval jev` it ties the `triage` model on type, and it is behind on priority, Value and Effort. Use `shadow` to measure it on real new issues. A config file is read as YAML 1.2 ([configuration reference](../CONFIGURATION.md)), so `jev: off` and `jev: on` with no quotes are the modes `off` and `on`. A bool, such as `jev: true`, is not a mode, and the settings do not load.

One request holds a question for each field that has a fixed list:

| Field | Question | Answer |
| :--- | :--- | :--- |
| Type | Pick one of the `type/*` labels of the package (`roadmap/workflow_labels.py`). Asked only when the title and the issue give no type. | The label |
| Priority | Pick one of `P1-High`, `P2-Medium` and `P3-Low`. | The priority |
| Value, Effort | Score a rubric of three levels. | The level, rounded |
| Duplicate | One yes/no question for each nearest item. | A possible original, when the probability reaches 0.90 |

### Mode `on`

Jev writes no text, so the reason lines say which option Jev chose and how sure it was. Jev gives no evidence for a P0 and no related item. The proposal goes to the same checks as the proposal of the `triage` model, so the checks decide which values stand, and a flagged duplicate only flags: the candidate is still placed.

Intake uses the `triage` model for the whole proposal when a Jev request fails, times out after 30 seconds, or gives a choice or score with a confidence below 0.60. The counter `devops_cli_roadmap_intake_jev_fields_total` shows, for each field, how often Jev (`jev`) or the fallback (`fallback`) gave it.

Do not set `on` before `devops roadmap eval jev` shows that Jev flags no more false duplicates than the `triage` model, and before the shadow report supports it. The command runs both models on the duplicate cases and on 25 closed issues with the labels a person set, and stops before its first call when it needs more calls than `--max-calls`. With `--min-confidence`, it counts a Jev answer below that confidence as no answer, as intake does at 0.60; the default 0 takes every answer to measure what Jev knows.

### Mode `shadow`

After the `triage` model answers and the checks of intake accept the reply, intake asks Jev the same questions, one request for each candidate (about 0.0001 USD). The text of the title and the issue goes to the hosted model, as in any model call of intake, and intake refuses a candidate that holds a secret before it. Jev changes nothing: no label, no flag and no comment come from it. A Jev error or timeout changes nothing too. It only counts.

Intake records the observation in the job record of the issue, as the mark `intake.jev_shadow`, in the same write as the Priority. The mark is compact JSON that holds the time of the proposal and, for each field, three values: the Jev answer, its probability, and the `triage` answer. For the duplicate, the Jev answer is the nearest item that reaches 0.90 (or empty), the probability is the highest one of any nearest item, and the `triage` answer is the possible original that intake took (or empty). The probability is from 0 to 1: the report counts a mark with another value as unreadable and goes on. The mark holds no text of the issue. A candidate that Jev could not answer has no mark.

Shadow counts in the same counter as mode `on`, `devops_cli_roadmap_intake_jev_fields_total`, with its own values of the label `outcome`: `agree`, `differ` and `jev_error`. The label `field` is type, priority, value, effort or duplicate. Mode `shadow` writes at most 15 series for each pod, mode `on` at most 10, and the counter has at most 25.

To read the records, run:

```text
devops roadmap eval jev --from-shadow
```

The command reads every issue of the repository (GitHub reads, no model request, no write). For each field it prints how often Jev and the `triage` model agree, how often each equals the label the issue holds now, how often only one of them does, and how often Jev is right in each band of its probability (below 60%, 60 to 75%, 75 to 90%, 90% and above). For the duplicate it counts the flags of each model against the issues that GitHub shows closed as a duplicate. The final label is a weak truth: intake writes the `triage` label, and a label that no person changed counts as final. Read the columns "only Jev" and "only triage" first.

## The issue listing

Intake compares each candidate with every item and with every issue closed as not planned, so each run needs every issue of the repository. Intake keeps a snapshot of the issue listing in `roadmap/listing/<owner>/<name>.json` under the data directory: `devops roadmap intake` on a workstation, and the intake rounds of the triage lane and the scoped intake of each delivery in the Service, on its volume. The snapshot holds the parsed record of each issue and pull request, the schema key of the records, the time of its last full read and a watermark. The schema key is the first 16 hex characters of the sha256 of the JSON schema of `IssueRecord`, so a release that keeps the record schema keeps the snapshot.

- A run reads only the issues and pull requests that changed since the watermark: `state=all`, `sort=updated`, `direction=desc` and `since=<watermark>`. Each changed issue replaces its record, so intake parses only the bodies of the changed issues. When 100 or fewer issues changed, the read is one request.
- The new watermark is the earlier of the start of the read and the newest `updated_at` that GitHub gave, less 60 seconds. Thus a local clock ahead of GitHub's clock skips no change.
- GitHub does not move the `updated_at` of a parent when a sub-issue joins or leaves it. A changed issue that joined or left a parent moves the sub-issue count of that parent by one.
- A run reads the whole listing and writes a new snapshot when no snapshot is kept, when the snapshot cannot be read, when its schema key is not the current one, when its last full read is 24 hours old or older, and on `--full`. The full read removes an issue that left the repository.
- The snapshot is a copy of GitHub, which stays the source of truth. A snapshot that intake cannot read or write gives a warning. A failed write keeps the earlier file, because intake writes a temporary file and renames it.

In the Service, the triage lane runs its intake rounds and the scoped intake of each delivery one at a time, so one writer keeps the snapshot of each repository. Thus a scoped round with a kept snapshot sends one listing request when 100 or fewer issues changed. The poll still reconciles each change that moved an `updated_at` (ADR 0017), and the full read of each day removes an issue that left the repository. The status lane reads every issue through a snapshot of its own, in `listing-status` of the state directory, which only its worker writes (#4854). The model lane reads the whole listing. `SnapshotStore` in `src/devops_cli/roadmap/stores/listing_snapshot.py` is the seam for a store that the pods of the Service can share (#4517).

## A failed write

A write of GitHub can fail for one candidate, for example with a status 502. Intake skips that candidate, places the others, and then the run fails and names it.

The Service keeps the failure in its intake record, beside `schedule.json`, and not in the job record of the issue. The issue is a candidate, not an item, so it gets no mark. The record holds the step (`place`), the failure class (`ci_infra` for an error of GitHub), the count of failures in a row and the time of the last one. The next rounds leave the candidate out until the wait of the class has passed (`RETRY_AFTER` in `roadmap/failure.py`: 1 hour for `ci_infra`). They make no triage call and no embedding call for it, and the candidate does not make intake due. After the wait, intake decides the candidate again. A candidate that is placed, closed or no candidate any more loses its entry. A change that a person made to the Item while the job worked is no failure and leaves no entry. A webhook update of the issue keeps the wait, and `devops roadmap intake` keeps no record, so it waits for nothing.

## When the Service runs intake

The Service runs intake as the row `intake` of the triage lane. A webhook delivery of `issues` `opened`, `edited` or `reopened` runs intake of its one issue at once (ADR 0017). The poll runs the whole job when one of these is true:

- The last run is as old as its interval or older: `roadmap.intake.interval_minutes`, 29 minutes by default, or `roadmap.intake.backlog_interval_minutes` while the last run counted `roadmap.intake.backlog_threshold` or more candidates (#5470).
- An issue reopened since the last run.
- The last run left a fresh candidate.
- The repository has an issue newer than the newest issue that a run saw.

The issue events report no opened issue, so the poll reads the newest issue from the first page of the issue listing, newest first, 10 entries a page. The read is conditional, so a page that did not change costs a 304. A pull request does not count. An issue that 10 or more newer pull requests push off the page waits for the interval of the row. The intake record keeps the newest issue that a run saw, as it was when the run started. A scoped update does not change it, so the poll still runs intake when a delivery of an older issue was lost. When a scoped update already decided the new issue, the run does not decide it again and sends no model request for it.

## The three modes

| Flag | What the run does |
| :--- | :--- |
| `--dry-run` | Makes no request to GitHub or to a model. It prints the requests that a run makes. |
| `--plan` (the default) | Reads GitHub and calls the model. It writes nothing. It prints each planned change and what the run spent. |
| `--confirm` | Plans as `--plan` does, then makes the writes. |

## The retitle job

`devops roadmap retitle` shortens the title summary of open items that has more than 60 characters. The stage job and the implement job leave out such an item, and the check `Semantic PR title` refuses its delivery title. The job also corrects a title type that the branch types do not list. The stage job leaves out an item with such a type, because its branch has no type.

- It takes the open items whose title has a Conventional Commit type and a summary of more than 60 characters, and the open items whose title type is not listed, also with a short summary. It takes the lowest number first, at most `--limit` (25) in a run. `--item` names one item.
- For a listed type, it keeps the type and the scope and writes only the summary. The new title passes `title_problems` of `src/devops_cli/roadmap/pull_form.py`.
- For an unlisted type that has a correction in the table of `src/devops_cli/roadmap/commit_title.py`, it writes the correction in place of the type and the scope, and keeps the summary: `security(ssh): x` becomes `fix(security): x`. It makes no model call for a short summary. It shortens a long summary of the corrected title in the same run, as for a listed type. When it cannot shorten it, it writes the corrected title with the old summary, and a later run shortens it. The comment names the old type and the types of the project.
- For an unlisted type that has no correction, it does not change the title. It comments once with the type and the types of the project, and a person edits the title.
- A Planned item takes the summary of the title of its plan pull request (`plan #<issue> <summary>`), which its job record names. The job makes no model call for it. When that title gives no valid summary, the job leaves the item and comments the reason once.
- Another item gets one request to the `triage` model, and one more with the faults of the first reply. A reply that fails twice leaves the item.
- It leaves a title that someone changed after the last comment of a job. It reads the title changes on the timeline of the item. When that title has an unlisted type, it comments once with the type, because the stage job cannot take the item.
- When it leaves an item (a person's edit, no plan title, no usable reply of the model, or a type with no correction), it writes the mark `retitle.skipped` once. It also writes one warning log line with the reason key: `invalid-title-type` for an unlisted type, else `long-title`. The value of the mark is a hash of the title, the body and the `stage.pr` mark. The selection leaves the item out while the hash holds, so a later round reads nothing of it and makes no model request for it. A change to the title, the body or `stage.pr` selects it again. A comment does not.
- Without `--confirm` it prints the new titles and writes nothing. With `--confirm` it writes each title and one comment with the marker `<!-- devops roadmap retitle -->`. `--dry-run` makes no request.
- The Service runs the job as the row `retitle` of the model lane. The row is due on a first run and every 61 minutes. The stage Jobs that the status lane submits read the new titles. Each run takes at most 25 items and writes as `--confirm` does. The row needs no clone.

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| Duplicate verdict, report lines, no close, retry of a stopped run, the source of a part | [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
| Type and scope labels from the title | [roadmap-intake-title-labels](../../openspec/specs/roadmap-intake-title-labels/spec.md) |
| What the reason comment holds | [roadmap-intake-reason-comment](../../openspec/specs/roadmap-intake-reason-comment/spec.md) |
| The reply of the model | [roadmap-intake-reply-schema](../../openspec/specs/roadmap-intake-reply-schema/spec.md) |
| The snapshot of the issue listing and the read of the changed issues | [roadmap-intake-listing](../../openspec/specs/roadmap-intake-listing/spec.md) |
| Intake of one issue on an `issues` event of GitHub | [roadmap-scoped-updates](../../openspec/specs/roadmap-scoped-updates/spec.md) |
| The disk cache of the embeddings | [embedding-disk-cache](../../openspec/specs/embedding-disk-cache/spec.md) |
| Jev for the proposal fields, and the comparison with the `triage` model | [roadmap-intake-jev](../../openspec/specs/roadmap-intake-jev/spec.md) |
| The evaluation of the duplicate verdict | `devops roadmap eval intake`, in [roadmap-intake-duplicates](../../openspec/specs/roadmap-intake-duplicates/spec.md) |
