# Proposal: #4803

## Why

Closes #4803. The Dependencies section of an issue body can name an issue by its quoted title, such as `- "feat(roadmap): run each refine item in its own pod".`. Refine and the stage job read only `#N` words in that section. So #4574 names 4 open dependencies by title, refine recorded "None", and the stage job can take #4574 before its dependencies merge. A plan that stage makes on such an item fails later, or builds on code that is not merged.

## What Changes

- `title_dependencies` in `src/devops_cli/roadmap/refine/refine.py` reads each quoted Conventional Commit title in the Dependencies section of the person's text. It matches the title exactly to the one open Item with that title, else to the one closed Item with it. A list item or paragraph that names `#N` is read by its number only.
- Refine adds each matched issue to the dependencies of the validated proposal. An open one blocks the item, and the refine section lists it.
- A quoted title that names no Item, or two Items, fails the round with the job check `dependencies`. The error names the title and asks for `#<number>`. Refine writes no comment, and a later round tries again.
- The stage job leaves out an item that names an open issue by its quoted title, as it does for `#N`.

The change alters what refine records and what stage leaves out, so it carries spec deltas for `roadmap-refine` and `roadmap-stage`. It fits one pull request.

## Capabilities

- `roadmap-refine`: a dependency named by title, and the job check `dependencies`.
- `roadmap-stage`: the stage job leaves out an item with an open dependency named by title.

## Impact

- 26 of 439 open issues in the census of 2026-11-11 name 57 dependencies by title. 20 of them name no `#N`, so refine and stage found no dependency for them. With this change, 23 issues get 44 open dependencies that refine and stage did not see. 2 Ready items (#4574 and #4545) leave the stage queue until their dependencies close.
- The stage job reads the listing of Items once a run for the titles. The GitHub store caches the listing, so it sends no new request.

## Feasibility

- The body of #4574, read through `devops gh api` on 2026-11-11, holds 4 quoted titles under `### Dependencies`, and its refine section holds `### Dependencies` then `None.`.
- `body_dependencies` in `src/devops_cli/roadmap/refine/refine.py` keeps only words that start with `#` and digits, and the refine proposal takes its dependencies from the model.
- A probe over the census of open issues with the new function resolved all 57 titles: 44 to open issues and 13 to closed ones. The 13 closed titles are delivered issues, found by a title search of the repository. So a match that reads only open issues would fail 9 issues with no cause.

## Existing Tool Considered

`markdown-it-py` already parses the Dependencies section, and the change reuses it. No open tool maps a title to an issue of the project listing. Cost to build: about 50,000 tokens and 1.5 hours to write, keep and fix. The change deletes no internal code: the `#N` word reader moves into `_issues`, which both readers share.
