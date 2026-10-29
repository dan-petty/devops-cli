# Design

## Decision

| Text | Shape | What enforces it |
| :--- | :--- | :--- |
| Pull request title: the squash subject and the changelog line | `<type>(<scope>): <summary>`, with a summary of at most 60 characters that states the effect | The `Semantic PR title` check, a required check of `main` |
| Pull request body: the squash message | What the change does and why, in at most 1,000 characters before the trailers; no measurements, rejected alternatives or file lists that the change folder holds; test results and steps in a comment | A reviewer; #2585 adds a warning in `devops pr check-readiness` |
| Commit on a topic branch | A Conventional Commit | Nothing: the squash merge replaces it |
| Reply, comment, issue text and other agent prose | ASD-STE100, with the result and the decision first and only the detail that the reader needs | The style rules that AGENTS.md rule 9 names, which every free-text model call also gets |

A reader first needs the result and the decision. The detail stays one link away: the `Change:` line of the body links the archived change folder, which holds the evidence and the rejected alternatives.

## Rejected alternatives

- **A limit on the whole title.** The action has no length input. Its `headerPattern` input could carry a look-ahead for the length, but a title that fails it gets the parse error "No release type found in pull request title", which does not name the length. `subjectPattern` checks the summary, and `subjectPatternError` names the limit.
- **A summary of at most 50 characters,** after git's guidance for a whole first line. Only 19 of the 188 recent summaries meet it, and a changelog line of 50 characters cannot say the effect of most changes. 60 characters with the median prefix of 13 gives a title near the 72 characters that gitlint uses.
- **A title limit of 100 characters,** the `header-max-length` of commitlint's conventional preset. 117 of the 188 recent titles already meet it, so it changes little, and the problem is length.
- **A `commit-msg` hook (commitlint or gitlint).** The squash merge replaces every commit on a topic branch, so a hook checks text that never reaches `main`, and it costs time on each commit.
- **A blocking check on the body length.** No open tool checks it, and a gate on prose would refuse a correct change for its wording. A person decides on a long body; #2585 adds only a warning.
- **A ratchet on task file size.** Task files no longer exist: OpenSpec change folders replaced them, and `openspec/config.yaml` holds their rules.
- **The shape in AGENTS.md.** AGENTS.md keeps one rule in one document and sends pull request titles to `CONTRIBUTING.md` and prose rules to `style_ste100.md`. A second copy in AGENTS.md would drift.
