# Design

## The message

`build_step_inputs` adds the rules before the item: one section "Rules of the repository (AGENTS.md)", then one section for each routed document. The first section is the text of `AGENTS.md` with no change. The step and the stage measure call one function, `step_rules.rules_sections(source, group)`, and get the same list of sections. So the measure cannot differ from the message.

## The routes

`ROUTES` is a tuple of `Route(row, patterns, document, sections)`:

| Pattern | Document | Sections |
| :--- | :--- | :--- |
| `tests/**` | `docs/TESTING.md` | Which change gets a test, Doubles, Layout |
| `src/**` | `ARCHITECTURE.md` | The architectural standards 1, 2, 3 and 5 of section 7 |
| `src/**` | `CONTRIBUTING.md` | Development Philosophy and Core Invariants, Naming |
| `src/devops_cli/security/**` | `SECURITY.md` | Zero-Trust Security and Egress Safety Principles |
| `src/devops_cli/roadmap/**` | `docs/ROADMAP_WORKFLOW.md` | Purpose, Labels and record keys, The stop and retry path |
| `k8s/**` | `k8s/README.md` | Stacks Overview, Directory Structure, Image Pins |
| `tf/**` | `tf/README.md` | the start of the document |

`row` is the exact "When you" cell of the row of `AGENTS.md` that sends a reader to the document. The code does not use it. The drift test uses it: it finds the row in the table, and checks that the row links the document. A change of a row, or a move of a document, fails that test. The paths that a group names are the code spans of its tasks (`TaskGroup.named_paths`), with a `::test` suffix removed. A path that does not exist yet counts, because a new test file is a test change.

## Why sections

A whole document is too large. `docs/TESTING.md` has 12,048 tokens, and a step with a test and a source file would add 21,500 tokens of three documents to a budget of 40,000. The sections above total 2,600 to 3,000 tokens each. A test checks that no selected text is cut by the cap, so the cap is a limit and not a silent loss. A route with no sections gives the start of the document, cut to the cap as a packed file is.

## Rejected alternatives

- **Give the whole routed documents.** `docs/TESTING.md` (12,048 tokens) plus `ARCHITECTURE.md` (4,697) plus `CONTRIBUTING.md` (4,831) is 21,576 tokens for a step that changes a test and a source file. With `AGENTS.md` (1,667) it leaves less than 17,000 of the 40,000 token budget for the item, the change folder, the group and its files. Measured on the three real groups, the plans would split into more groups. Rejected for cost.
- **Give the start of each document up to the cap.** `ARCHITECTURE.md` starts with six sections of the system overview (about 1,500 tokens) and holds its coding standards in section 7, which the cap would cut. Rejected because the part that a coder needs is at the end.
- **Give a list of headings and let the agent open the sections.** The agent then reads a document only if it decides to. The 13 stops of 2026-11-01 show that it does not follow a rule it does not see. Rejected.
- **Choose the documents with a model call.** It costs a request for each step, and a model can skip a document. The path of a file decides the kind of change without a model. Rejected.
- **Read the documents of a row from `AGENTS.md` at run time.** The row "write code" also sends a reader to `CONTRIBUTING.md` for a change to a command, and the row "change a manifest" lists `tf/README.md` for OpenTofu. A row does not hold a path pattern or a section. So the table in code is needed, and the test keeps it in step with the rows.
- **Copy the rules into the prompt, as today.** This is the cause of the drift: nesting of 5 in the prompt, 4 in `CONTRIBUTING.md`. Rejected.
- **A check that the prompt states no rule at all.** A test cannot tell a rule from the runner facts. The test compares what it can compare: the `.data/` paths of the prompt against those of `AGENTS.md`, and a list of the rule texts that the prompt dropped.

## The measure

`measure_groups` adds the tokens of `rules_sections(root, group)` for each group. `AGENTS.md` counts once for each group, as each step reads it. A root without `AGENTS.md` adds nothing, so a repository without the file keeps the old measure. The step prompt is not in the measure today, and this change does not add it.

## The rules are data and are bounded

The rules text comes from the branch, and an earlier step can edit it. So the prompt says that the rules are data, and that its own instructions win over a rule that conflicts with them. `AGENTS.md` describes the work of a person and of the job (commit, push, archive, pull request, `devops roadmap return`, the full `devops ci`), and the agent does none of it. The prompt lists that work and says the job does it. The `AGENTS.md` text is cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens, as a routed document is, so a large file in a branch cannot fill the window. The real file holds about 1,700 tokens, so the cut does not touch it. The text keeps its place under its own heading, and a heading inside it is data under the rules heading. The test builds a message from a hostile `AGENTS.md` and checks that the instructions stay the prompt.

## Missing files

A checkout with no `AGENTS.md`, or a route whose document is missing, adds no section. The file is the state of the repository. The drift test fails in this repository when a route points to a missing file or to a section that the document lacks. A route with no sections gives the start of the document, cut to the cap.

## Measured cost

`build_step_inputs` was run on every group of the corrected plans of #2175, #2462 and #2531, on `origin/main` and on this change, with the real issue text and a window of 128,000 tokens (the exact tokenizer):

| Plan and group | Names | Before | After | Added |
| :--- | :--- | ---: | ---: | ---: |
| #2175 group 1 | `src/` | 8,765 | 15,751 | 6,986 |
| #2175 group 4 | `src/` | 12,668 | 19,654 | 6,986 |
| #2462 group 1 | `tests/` and `src/` | 10,980 | 20,700 | 9,720 |
| #2531 group 1 | `tests/` | 6,733 | 11,063 | 4,330 |
| #2531 group 2 | `tests/` | 9,000 | 13,330 | 4,330 |

`AGENTS.md` adds about 1,700 tokens to each. Each routed document adds 2,500 to 2,900 tokens. The largest of these five groups is 20,700 tokens. A second measure ran over all 1,392 groups of the plans in `openspec/changes` and `openspec/changes/archive`. Before this change no group passes `roadmap.stage.step_tokens` (40,000). After it, two groups pass: group 1 of `2526-the-five-defect-fixes-merged-on` (31,133 before, 43,816 after) and group 1 of `2167-the-49-test-files-that-no` (30,666 before, 43,349 after). The most that the rules add to one group is 14,248 tokens. A new group with a heavy body can pass the 40,000 budget, and then costs one more split request in the stage job. The step still fits: 43,816 tokens and the prompt are far below the window of 128,000 minus the reserve, so no step breaks. The owner may raise the budget; this change does not.

## Score of the implement eval

`docs/ROADMAP_WORKFLOW.md` asks a change of the implement prompt for the score of `devops roadmap eval implement` on the base and on the branch. A run of the 14 fixtures takes about two hours on each side, so this change ran one fixture, `2531-cwd-guard-first-plan`, on the model `devops-coder`:

| Side | Status | Properties passed | Requests | Input tokens |
| :--- | :--- | :--- | ---: | ---: |
| Base | stopped (`ruff check` on a new test file) | 2 of 4 decided: `tests_kept`, `no_scratch` | 74 | 2,644,579 |
| Branch | stopped (`mypy --strict` on a test file) | 2 of 4 decided: `tests_kept`, `tasks_ticked` | 49 | 1,257,569 |

A first base run ended after 11 requests with the known Ollama tool-call parse error (`ollama/ollama` 18563) and is not counted. One run on one fixture does not show a gain or a loss. The rules reach the agent in the first request (the tests show it). A person decides whether to run the other fixtures.
