# Design

## Context

`collect_context(source, sha, body, max_tokens)` builds the text that the stage job (`StagePlanner._request`, budget `window // 2`) and the refine round (budget: the context window of the `analysis` task) give the model. `truncate_to_token_limit` cuts the end of the text when it is over the budget. The sections stand in this order: `CONTEXT.md`, up to 5 ADRs, the cited code, the identifier lines, the tree.

## Decisions

### Sections and their order

Two kinds of section are new: "Tests and callers of `<ident>`" for each cited identifier, and "Requirements of `<capability>`" for each spec that covers a cited file. They stand after the ADRs and before the cited code. The cut of the budget takes the end first, and a cited file can be 60,000 tokens long (`refine.py` alone is 2,300 lines), so a section after the code would be the first thing lost. The new sections are short and bounded, so they push the code down by at most the worst case below.

### The bound is on paths, 50 for each symbol

`CONST_ROADMAP_REFINE_MAX_PATHS_PER_SYMBOL = 50`. The tests come first, then the callers, so a cut removes callers before tests: the issue's failures were missed tests. The section says "(N of M paths shown; K more left out)" when it cuts. The 20-line cap of "Identifier matches" stays, because those lines show how a symbol is used.

Rejected:

- Keep 20. A symbol named in 10 source files and 10 test files would lose its tests. On this checkout, `run_subprocess` is named in 155 Python files, so even 50 cuts it; the note says so.
- 100 paths. The section of `run_subprocess` at 50 paths is 494 tokens, so 100 paths would double the cost for the symbols that need it least, and a model does not read past the first dozen paths.

### Only Python files, only the cited identifiers

The search uses the pathspec `*.py`. The symbols that items cite are Python names. Without the pathspec, a name such as `config` or a task title brings in the archived change folders, which name every symbol of every closed item. The search takes the same identifiers as the existing greps (backticked, at least 3 characters, the first 5 in sorted order), so the number of git calls grows by at most 5.

### A test file

A path under `tests/`, or a name that matches `test_*.py` or `*_test.py`. Rejected: `pytest --collect-only`. It needs the test runner in the Service image and takes seconds, while `git grep` takes milliseconds on a pinned commit.

### The base specs of a cited file

No stored mapping from a file to a capability exists (see Feasibility). Two rules need no stored data:

- Name: a module `src/devops_cli/<package>/<module>.py` has the key `<package>-<module>` (underscores become hyphens). A spec covers it when its name is the key, or the key starts with the name and a hyphen. So `roadmap/stage_eval_run.py` has the key `roadmap-stage-eval-run`, and the specs `roadmap-stage-eval` and `roadmap-stage` cover it, and `roadmap-stage-eval-run` would too.
- Path: a spec covers the cited file when its text names the path. One `git grep -l -F` for all cited paths in `openspec/specs` finds them.

The names come from the `### Requirement:` headings with one regular expression. Rejected: `openspec list` or `openspec validate` for the names. They need the `openspec` binary in the Service image and add a process, and the headings are plain lines. At most 5 specs and 40 names for each spec: `roadmap-refine` has 38 requirements, and the largest base specs have at most 65.

Rejected: a file list in every spec. It would give a full mapping, but it is a larger change that edits 162 specs and the stage prompt; see the follow-up in `tasks.md`.

## Measured token cost

The context was built for the body of #3012 (the sections "What happened", "What should happen" and "Acceptance criteria", and a line that cites `src/devops_cli/roadmap/refine.py`, `tests/roadmap/test_roadmap_refine.py` and the symbols `collect_context` and `run_subprocess`), on this checkout, with the `tiktoken` count that `count_tokens` gives (`gpt-4o` encoding):

| Part | Tokens |
| :--- | ---: |
| Tests and callers of `CheckFailure` (1 path) | 23 |
| Tests and callers of `collect_context` (3 paths) | 42 |
| Tests and callers of `install_tools` (7 paths) | 82 |
| Tests and callers of `run_subprocess` (50 paths, the bound) | 494 |
| Tests and callers of `split_offs` (3 paths) | 44 |
| Requirements of `roadmap-refine` (38 names) | 492 |
| **Added by this change** | **1,178** |
| The context before this change (two whole cited files included) | 68,593 |

The added part is 1.7 % of the uncut context of this item. The worst case is 5 symbols at 50 paths (about 500 tokens each) and 5 specs at 40 names (about 500 tokens each): about 5,000 tokens. The stage budget is `window // 2`, and the refine budget is the whole context window of the `analysis` task, so the worst case takes a fraction of either. The cut still holds the budget (`test_the_larger_context_stays_inside_the_token_budget`), and the added sections come before the code, so the code gives way first.

To measure again, build the context for an issue body with `collect_context(checkout, sha, body, max_tokens=10**9)`, and count the tokens of `_collect_symbol_sections` and `_collect_spec_requirements` with `count_tokens`.

## Risks

- A symbol that many files name (`run_subprocess`, 155 files) fills its 50 paths with tests of other topics. The note of the cut tells the model the list is partial. A person who cites a rarer symbol gets the full list.
- The name rule covers 6 % of the modules and the path rule 4 specs, so a cited file often brings no spec names. The sections that appear are right; the miss is a gap in the data (no file list in the specs), and the follow-up names it.
