# Proposal

## Why

Issue #1803: commit messages and other agent-written text are much longer than the project asks for, and nothing enforces a shape. Since ADR 0012 the squash merge takes the pull request title as the subject on `main` and the pull request body as the message, and release-please writes the title as the changelog line. So the title and the body are the history that a reader of `git log`, a review and the release notes reads.

## What Changes

- **Title.** The summary of a pull request title, the text after `<type>(<scope>): `, has at most 60 characters. The `Semantic PR title` check (`.github/workflows/pr-title.yml`) refuses a longer summary with the action's own `subjectPattern` and `subjectPatternError` inputs. `CONTRIBUTING.md` section 4 and its naming table state the rule. With the median `<type>(<scope>): ` prefix of 13 characters, a title stays near 72 characters.
- **Body.** The body says what the change does and why, in at most 1,000 characters before the trailers, and does not repeat what the archived change folder holds. `CONTRIBUTING.md` section 4 states the rule. A reviewer checks it. #2585 adds a warning to `devops pr check-readiness`.
- **Commits on a branch.** No hook checks them: the squash merge replaces them. `CONTRIBUTING.md` section 4 says so.
- **Other agent-written text.** `src/devops_cli/ai/tasks/style_ste100.md`, the rules that AGENTS.md rule 9 points to for every reply, comment, issue and document, gains one paragraph: put the result and the decision first, give only the detail that the reader needs, and do not tell the steps unless the task asks for them. The same file is the style request of every free-text model call, so the model's free text gets the same rule.
- **One owner.** `docs/SDLC.md` and `docs/ROUTINE_TASKS.md` each held a second "Concise, Effect-Driven Commit Messages" rule. Both now point to `CONTRIBUTING.md` section 4. The pull request template points there too.
- The change alters no command, option, message, manifest or service. It changes a CI workflow, documents and the text of the style request, so it has no spec delta.
- This change fits one pull request.

## Impact

- `.github/workflows/pr-title.yml`, `tests/test_workflow_contracts.py`.
- `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `.github/pull_request_template.md`.
- `src/devops_cli/ai/tasks/style_ste100.md`, `tests/__snapshots__/test_ai_client_style_request.ambr`.

## Feasibility

Measured on 2026-10-29 at origin/main `97ed0ea9`, with `git log --no-merges --format='%s%x1f%b%x1e' <range>`, release-please commits left out. A title is the subject without the ` (#<number>)` that GitHub adds. The trailers are the `Closes`, `Change:`, `Fail-to-pass:`, `Co-authored-by:`, `Signed-off-by:` and `Plans` lines.

| Range | Commits | Title median | Titles over 72 | Body median | Bodies over 1,500 | Longest body |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `954914e2..d09a0285`, the range of the issue | 50 | 82 | 40 | 0 | 8 | 5,540 |
| Squash commits from 2026-10-25 to 2026-10-28 | 191 | 91 | 146 | 1,300 | 83 | 12,621 |

- Over the 188 squash commits of the second range that are not dependency updates, the summary has a median of 77 characters, and 46 have 60 or fewer. The body before the trailers has a median of 1,287 characters, and 69 have 1,000 or fewer.
- The text got longer after the squash message became the pull request body (repository settings: `squash_merge_commit_title` `PR_TITLE`, `squash_merge_commit_message` `PR_BODY`).
- git's own guidance asks for "a single short (no more than 50 characters) line summarizing the change" (git-scm.com/docs/git-commit, Discussion). gitlint's default title limit is 72 characters.
- `amannn/action-semantic-pull-request` v6.1.1 has no input for a length. Its `subjectPattern` is matched against the parsed subject only, and the first match must cover the whole subject (`src/validatePrTitle.js`: `result.subject.match(new RegExp(subjectPattern))`, then `matchedPart.length !== result.subject.length`). So `^.{1,60}$` refuses a summary of 61 characters or more, and `subjectPatternError` replaces the default message.
- The issue asked for the shape in AGENTS.md. AGENTS.md has changed since: each rule lives in one document, its table sends "write a pull request title" to `CONTRIBUTING.md`, and rule 9 sends prose rules to `style_ste100.md`. The shape goes in those two documents, so AGENTS.md needs no change.
- The issue also measured task files and changelog fragments. OpenSpec change folders replaced the task files, and release-please writes the changelog from the titles, so neither exists now.

## Existing Tool Considered

- **Title:** the existing `Semantic PR title` check, with its `subjectPattern` input. Nothing is built.
- **Body:** no open tool checks the length of a pull request body. commitlint checks commits, which the squash merge discards, and markdownlint checks line lengths only. A reviewer checks the body. #2585 adds a warning to the existing advisories of `devops pr check-readiness`, with its written cost.
- **Agent replies:** no tool checks them. The rule goes in the style rules that agents and models already get.

This change deletes the two duplicate "Concise, Effect-Driven Commit Messages" rules in `docs/SDLC.md` and `docs/ROUTINE_TASKS.md`.
