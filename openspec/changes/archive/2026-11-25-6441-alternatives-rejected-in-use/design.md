# Design

## Decisions
1. **Option-title and head-noun-phrase matching in `rejects()` (`src/devops_cli/roadmap/adr.py`):**
   - Extract the subject title of each `Considered Options` list item (up to the top-level separator `:` outside inline code and links, or the leading bold heading sentence) and strip parenthetical tags such as `(runner-up)` or `(Kubernetes Jobs)`.
   - Parse inline Markdown without appending `link_open` `href` targets so URLs never trigger `rejects()`, while keeping `names()` unchanged for issue body matching (`test_a_text_names_a_tool_by_its_names_in_the_forms_that_say_so` at `tests/roadmap/test_roadmap_adr.py:292`).
   - Match full `owner/name` anywhere in the stripped visible option title.
   - For bare names, split coordinated clauses (`,`, `and`, `or`), ignore packaging-method gerund clauses (`bundling`, `vendoring`), drop trailing prepositional tails (`for`, `through`, `of`, `with`, `on`, `in`, etc. while preserving hyphenated forms like `in-process`), strip leading determiners/verbs, and confirm a bare name only when it is the head noun, is followed by a single version token (`APScheduler 4`), or is a multi-word product name followed by a lowercase non-`CLI` component/artifact word (`agent-sandbox controller`, `IBM Carbon tokens`, `GitHub Primer primitives`, `DBOS Transact in-process`). Single-word modifiers before a different head noun (`Kubernetes Lease`, ``Kubernetes `metadata.generateName` ``) and `CLI` qualifiers (`` `gh` CLI``, `CodeQL CLI`) return `False`.
2. **Verdict order and own-repository check in `alternatives.py`:**
   - Pass optional `repo: str | None = None` from `plan_alternatives` -> `_check_one` -> `validate_reply` -> `_verdict_of`, falling back to `project_of(item.url)` when `repo` is omitted.
   - Check whether the candidate tool's GitHub project (`tool.project or project_of(tool.url)`) or slug matches the item's repository first in `_verdict_of()` and return `(Verdict.IN_USE, None, True)`.
   - Then run `_confirmed_adr()`, then `inventory.uses()`, then `reply.in_use`, then `reply.verdict`. This keeps ADR 0018 `bubblewrap` as `rejected` while never marking the item's own repository as `rejected`.

## Rejected alternatives
- **Checking `inventory.uses()` before `_confirmed_adr()`:** Rejected because ADR 0018 explicitly rejects `bubblewrap` for the planner run tool while `.devcontainer/Dockerfile` installs `bubblewrap`, so checking inventory before ADR would suppress genuine path-specific rejections (`src/devops_cli/roadmap/alternatives.py:1189`).
- **Matching bare tool names only by full `owner/name`:** Rejected because ADRs reject bare tools such as `bubblewrap`, `gVisor`, `Temporal`, and `APScheduler 4` (`docs/adr/0008` and `docs/adr/0018`), which lack `owner/name` in option headings.
- **Keeping the ADR 0005 `github/codeql` census expectation `True`:** Rejected because ADR 0005 line 52 rejects `Vendoring Semgrep registry rules or bundling the CodeQL CLI` as a licensing/bundling restriction rather than rejecting CodeQL as a scanner (`docs/adr/0005-review-findings-come-from-tools-not-models.md:52`, `tests/roadmap/test_roadmap_adr.py:463`).
- **Special-casing `"CLI"` as a tool suffix:** Rejected because it would keep `` `gh` CLI`` as a match rather than separating a CLI wrapper/interface from the underlying tool subject (`docs/adr/0006-github-session-requests-go-through-gidgethub.md:29`).
