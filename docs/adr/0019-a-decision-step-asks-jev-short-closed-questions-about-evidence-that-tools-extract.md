---
status: accepted
date: 2026-11-09
decision-makers: [owner]
issue: 4326
amended-by: ["0020"]
body-hash: 7350fe6b7ca479150f59a95dfda2eec2aa3acaaf642b160b53fc3f27fc0fb81b
---

# A decision step asks Jev short closed questions about evidence that tools extract

TypeSafe Jev (`typesafe/jev-1.14`) is a System One decision model. It answers typed questions about a text with a calibrated probability, and it writes no text. It is no drop-in replacement for a model that writes. On 2026-11-10 the owner decided that the workflows must change to fit a decision model. This record decides how a workflow uses Jev. It builds no code.

## Context

Three trials used Jev as a cheaper model. All three failed their gates.

- **The completeness check of a draft pull request** (#4320, switch off) gave 28% false holds and 43% recall. The probability moved 0.02 or less when one hunk left a long diff that was given as state. Jev did not read the long state.
- **The labels of an intake proposal** (#4323, switch off) are behind the triage model on priority, Value and Effort. They found 0 of 3 true duplicates. The thresholds (0.90 and 0.60) were guesses. The confidence of a score was 0.25 to 0.55.
- **The screen before the verify step** (#4282) had a guessed threshold (0.05) and no data.

What the trials share: each one gave Jev a long text and asked a broad question, and each one set a threshold by hand. Jev works on short, closed questions, as `devops ai ask-jev` shows.

## Decision

A **decision step** is a place in a workflow where the workflow must pick one of a few known outcomes, and Jev gives evidence for the pick. A decision step follows seven rules.

1. **A decision point, not a generation point.** A decision step picks an outcome from a closed set: skip or run, a class from a fixed list, a tier. It never writes a plan, a comment, a quote or code. A step that needs a quote or a text stays with a model that writes.
2. **Tools extract the evidence. Jev judges a short digest of it.** Code builds the evidence: the hunk, the path, the quoted line, the test name, the criterion, the fact of a tool call. The digest holds these facts and short pieces, each cut to a size limit. A fact that a tool found, such as "this path is not in the repository", goes into the digest as a fact. A long document is never the state of a question.
3. **Many small questions in one request.** The questions about one digest go in one `DecisionRequest`. A request that asks nine questions about one digest costs a ninth of nine requests, and in pilot 1 it ranked the cases as well as nine requests did. The question set of a step is fixed in code and has a test.
4. **Thresholds are fitted, not guessed.** A fit script sets the cuts from labelled data. The cases are in two fixed halves. The script fits on one half and reports on the other, and then repeats with the halves swapped. The fitted values are data in the repository, with the date, the model, the cases and the numbers that gave them. A cut in a constant is a guess, and a test refuses it. The fit is made two ways, a cut for each question and one cut for all questions, and the report gives the loss of both on the half that was not fitted. In pilot 1 each half held about 24 cases. With the recorded split, one shared cut lost no serious defect in either direction, and a cut for each question lost 6 in one direction. With an earlier split, the result was the reverse for one case. The loss moved with one case. A half of that size is weak evidence, and the report says so.
5. **Action bands, not pass or fail.** A step has at least three bands: *continue* (the existing path goes on, or the cheap path is taken), *send to the reviewer* (the costly path runs) and *flag* (a person or the log sees the case). The band follows the fitted thresholds.
6. **Shadow first. Fail open.** A step first runs in shadow: it logs and counts its decision beside the real result and changes nothing. A person turns a step on after reading the shadow log and the fit report. A switch is off by default. An error, a timeout, a missing answer or a confidence below the fitted floor sends the case to the existing path.
7. **A Jev answer is evidence, never the only control.** A step never approves, rejects or merges alone. It is never the only security control. Its input can hold text that misleads it, so a step that skips a check also keeps a deterministic check that does not depend on Jev.

### The measure of a step

A step has a success bar that is fixed before the fit. The bar names the loss that is allowed, the saving that must follow, and the cases on which both are counted. The labelled data bounds the saving: the share of cases that need no run, which the report calls the oracle, is the most that any screen can skip with no loss. A bar is checked against its oracle before the first fit, and a bar above the oracle is not set. The report of a step gives the same numbers for the halves that were fitted and for the halves that were not, and it says what it cannot show.

### The shape in code

One small module holds the shared parts: the typed question set, the request builder, the fitted thresholds with their bands, the log record and the fail-open rule. A step supplies its evidence builder and its question set. The module reuses `create_jev_model` of `src/devops_cli/ai/jev.py`. It builds no second client.

## The candidate decision points, ranked by fit (replaced by the catalogue of ADR 0020)

| Rank | Decision point | Outcomes | Why it fits | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | The screen before the verify step (#4282): skip the tool-using reviewer, or run it | skip, run, flag | The outcome is binary. The golden set labels the defects. The reviewer is the fallback. A skip saves an agent run. | Pilot 1 |
| 2 | The class of a failure when no regex rule matches (`src/devops_cli/roadmap/failure.py`) | one of the 19 `FailureClass` values, or `ci_infra` | A closed choice. The default is known. The stored failures are labelled by their typed causes. | Pilot 2, no go: a rule fixes it (#4390) |
| 3 | The tier of a stage run (#4284) | tier, high risk | A closed choice with a score. The real result is the label. | Shadow only, after the pilots |
| 4 | The `type/*` label of an intake item when the title gives none | one of the type labels | A closed choice over a short title. | Later, with bands |
| 5 | A tool call of an agent (`gate_tool_call_with_jev`) | run, review, block | Short evidence: the tool name and the arguments. | Never alone: it adds to a deterministic control |

## What is not suited

- **Any step that writes**: a plan, a pull request body, a comment, a finding or a quote. A finding that can stop a plan needs a quote from the input (`open_findings`), and Jev gives none.
- **A judgment of a long text as state**: the completeness of a diff (#4320). The answer did not follow the text.
- **A duplicate search**: a true duplicate is rare, and the answer needs the nearest items as evidence. Intake found 0 of 3 true duplicates with Jev. A decision step may flag a pair that an embedding search proposed. It does not search.
- **Priority, Value and Effort of an item with a guessed threshold**: the triage model leads on them. They return only with fitted thresholds and a *flag* band.
- **A question that needs the repository**: an agent with read tools answers it. A decision step may screen before such an agent. It does not replace the agent.
- **A security control used alone**: see rule 7.

## The pilots and their bars

The data of pilot 1 is the golden set of the stage job: 56 cases, 51 plans with 317 labelled defects and 5 good plans. A fixed split makes two halves. The reviewer is the model of the task `verification` (run with `deepseek-v4.1-flash-1017` for the baseline).

- **Pilot 1, the verify screen (#4282).** The screen decides before the reviewer runs. The cascade passes when, on the half that was not fitted, it loses no serious defect (blocker or major) that the reviewer alone finds on the same cases, **and** it skips at least 30% of the reviewer calls. The report also gives the false-clear rate and the cost of a plan with and without the screen. If the bar is not met, the setting stays off and the report states why, with the numbers and the best design found. The pull request of #4282 measured this bar. The reviewer alone found no serious defect in 9 of the 48 cases that it could review (19%), so the oracle of the golden set is below 30%, and no screen could meet the bar. A later bar for the same step must come from the oracle of its data.
- **Pilot 2, the failure-class tail (measured on 2026-11-10: no go).** `classify_failure` in `src/devops_cli/roadmap/failure.py` is a pure function of the evidence, and a failure that matches no rule is `ci_infra`. The 271 stop comments of the four repositories of the Service since 2026-10-11 held 8 untyped stops, and 4 of them were one pattern. A typed class fixes that pattern by rule (#4390), and a rule beats a model call on a tail of this size. The pilot builds no step. It returns only if a larger untyped tail appears.

## Considered Options

- **Use Jev as the model of each step that a cheaper model could serve**: rejected. Three trials show that Jev does not write and does not read a long text.
- **Guess a threshold and tune it after a switch is on**: rejected. It was the cause of the failure of #4323 and #4282.
- **One rule for the cuts, fixed in advance**: rejected. Questions differ in base rate and scale, but a half of 24 cases cannot fit nine cuts. The fit runs both ways and the report shows both.
- **Replace the reviewer**: rejected. The reviewer reads the repository with tools and gives a quote. Jev does neither.
- **Wait for a better Jev**: rejected. The pattern holds for the next version, and the fit script repeats on its data.

## Consequences

- Each decision step is a small module on the shared parts, with a fit script, a data file of fitted thresholds and a shadow metric of bounded labels.
- A step that fails its bar stays off, and its report says why. The record does not promise a saving.
- The cost of a step is a Jev request for each piece, at about 0.042 USD for one million input tokens. The fit needs labelled data, and a step with no labelled data does not start.

## Status History

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md` names the merge commit. The pilot of the first decision step is issue #4282. The second step was measured and needs no model. [ADR 0020](0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md) amends this record in three places: it replaces the table of ranked decision points and the section of the pilots with its catalogue, it names the setting that holds the mode of a step, and it gives the measured result of pilot 2. The seven rules of this record stay in force.
