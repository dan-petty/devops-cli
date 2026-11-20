# Proposal

## Why

The stage job and the implement job read each `#N` under a Dependencies heading as an open dependency, so a parent link, a child link, a related item, a reverse link and the source line of intake hold Ready items back. #6451 reports 18 Ready items that never become Staged and 2 cycles that reverse links make. Only an issue that the item waits for must hold it back.

## What Changes

- `src/devops_cli/roadmap/refine/refine.py` keeps each `#N` of the Dependencies section as a blocker, also in prose, unless the text names a link: a block that starts with `None` or `No`, a `#N` after a link word (`Part of`, `Child`, `Tracker`, `Related`, `Source`, an owner decision), a sentence with a reverse phrase (`#N needs this item`, `This item blocks #N`, `#N is the parent tracker`), a block whose issue merges in either order, or a `#N` in parentheses with other words. The hold line `- #6521 (hold: ... of #6519)` names #6521 only.
- `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py` moves to the time of the fix, so a wait on a person that the older rule set gets one new round.
- The new test module `tests/roadmap/refine/test_roadmap_refine_dependencies.py` holds the blocker and the non-blocker forms of the reader, so the stage, implement and consolidate paths that read the one reader keep their behavior with no change of their own.
- `NewCandidate.filed_body` in `src/devops_cli/roadmap/intake/intake.py` writes the line `Source: <source>` under a `## Source` heading after the body, so the source names no dependency. `_new_subject` also finds an issue of the old form, which ends with the `Source:` line and no heading. The assertion of `tests/roadmap/intake/test_roadmap_intake_evidence.py` and the one of `tests/roadmap/intake/test_roadmap_intake_sub_issues.py` move to the new form.
- `docs/roadmap/refine.md`, `docs/roadmap/stage.md` and `docs/roadmap/intake.md` state the blocker rule, and that intake writes its source under `## Source`. The base specs `roadmap-stage/context` and `roadmap-implement-job/selection` read each blocker that the Dependencies section names.
- The change carries a spec delta, because the Dependencies section that a job of the service reads and the filed body of intake are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/waits`: An issue reference under Dependencies names a blocker, A link under Dependencies names no blocker, A non-blocker mention under Dependencies holds nothing back
- `roadmap-intake-writes`: The filed body names its source under its own heading
- `roadmap-stage/context`: The request lists the declared issue dependencies, The prompt names the declared dependencies (base spec text only)
- `roadmap-implement-job/selection`: The implement judge leaves out an open dependency (base spec text only)

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/config/constants.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/roadmap/intake.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_dependencies.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/intake/test_roadmap_intake_evidence.py`, `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`, `tests/roadmap/intake/test_roadmap_intake_agent_candidates.py`

## Feasibility

- The probe says: The path `src/devops_cli/roadmap/refine/refine.py` is a file of the staging commit, and the reader that this change rewrites is `def body_dependencies(body: str) -> list[int]:`. `read_file src/devops_cli/roadmap/refine/refine.py 1200 1250` showed `src/devops_cli/roadmap/refine/refine.py:1224:def body_dependencies(body: str) -> list[int]:` and `src/devops_cli/roadmap/refine/refine.py:1236:def _issues(token: Token) -> list[int]:`.
- `src/devops_cli/roadmap/refine/refine.py:1233:return [number for token in section if token.type == "inline" for number in _issues(token)]` keeps every number of every inline token of the section, and `src/devops_cli/roadmap/refine/refine.py:1239:return [int(word[1:]) for word in words if word.startswith("#") and word[1:].isdigit()]` looks at no word around the number, so `Part of #5014` and `Source: #4989` give a number today.
- `src/devops_cli/roadmap/refine/refine.py:1232:section = _section_tokens(MarkdownIt("commonmark").parse(body), _DEPENDENCIES_TITLE_RE)` shows that markdown-it-py parses the body, and `src/devops_cli/roadmap/refine/refine.py:1165:if token.type == "heading_open" and title_re.match(tokens[index + 1].content.strip()):` shows that the section ends at the next heading of the same or a higher level, so a `## Source` heading after the body ends the Dependencies section.
- The staged constants that the blocker rule uses are `src/devops_cli/roadmap/refine/refine.py:1156:_REFERENCE_PUNCTUATION: Final[str] = ".,;:()[]"` and `src/devops_cli/roadmap/refine/refine.py:1154:_DEPENDENCIES_TITLE_RE = re.compile(r"Dependencies\b", re.IGNORECASE)`.
- `src/devops_cli/roadmap/refine/refine.py:2107:lines.append(", ".join(f"#{d}" for d in proposal.dependencies))` shows that a refine round writes its dependencies as one line of issue references, so the reader must keep a line that holds issue references only.
- `read_file src/devops_cli/roadmap/dependencies.py 20 50` showed `src/devops_cli/roadmap/dependencies.py:35:*body_dependencies(item.body),` inside `def open_dependency(item: Item, store: RoadmapStore, items: Sequence[Item]) -> str | None:`, which the stage job and the implement job call, so the reader's rule reaches both jobs with no second change.
- `references` for `body_dependencies` gave `files 10, lines 15`: `src/devops_cli/roadmap/consolidate_shortlist.py` (lines 41, 174), `src/devops_cli/roadmap/dependencies.py` (lines 13, 35), `src/devops_cli/roadmap/refine/refine.py` (lines 1224, 4261), whose `src/devops_cli/roadmap/refine/refine.py:1224:def body_dependencies(body: str) -> list[int]:` is the reader that group 1 changes, and `src/devops_cli/roadmap/stage/stage.py` (lines 202, 2436); the other six are archive folders of older changes. The four source files are in a group's changes or in a decision below.
- The probe says: The path `refine.blocked_by` is no file of the staging commit. No commit in the history deleted or renamed it. The issue names a key of the job record there, not a path, so the plan cites no missing path.
- `read_file tests/roadmap/stage/test_roadmap_stage_selection.py 274 306` showed `tests/roadmap/stage/test_roadmap_stage_selection.py:279:waiting = _seed(store, body=f"### Dependencies\n#{blocker}, #{closed}\n")`, a paragraph of issue references that must stay a dependency.
- `read_file tests/roadmap/test_roadmap_consolidate_shortlist.py 160 176` showed `tests/roadmap/test_roadmap_consolidate_shortlist.py:174:assert [Signal.LINK in signals(lists, 3, n) for n in (2, 4, 5)] == [True, True, False]`, so a paragraph of two references names both and the rule must keep it.
- `read_file tests/roadmap/implement/test_roadmap_implement_selection.py 112 130` showed `tests/roadmap/implement/test_roadmap_implement_selection.py:123:- #{blocker}: the prerequisite`, a list item whose first word is an issue reference and whose text goes on, so the rule reads the whole item.
- `read_file src/devops_cli/roadmap/intake/intake.py 200 240` showed `src/devops_cli/roadmap/intake/intake.py:227:return f"{self.body}\n\nSource: {self.source}" if self.source else self.body`, which appends the source line to the end of the body, so a source that names `#4989` lands under the last heading of the body.
- `read_file src/devops_cli/roadmap/intake/intake.py 688 708` showed `src/devops_cli/roadmap/intake/intake.py:698:body = new.filed_body()` in `_new_subject`. The issue side of that match is the body on GitHub, so an issue filed before the change keeps the old form, and the match must accept both forms.
- `read_file tests/roadmap/intake/test_roadmap_intake_evidence.py 60 110` showed `tests/roadmap/intake/test_roadmap_intake_evidence.py:93:body.endswith("Source: https://example.test/review/1"),`, and `read_file tests/roadmap/intake/test_roadmap_intake_sub_issues.py 170 196` showed `tests/roadmap/intake/test_roadmap_intake_sub_issues.py:187:assert (outcome, sent, [body.endswith(f"Source: {source}") for body in bodies]) == (`, so two tests pin the filed-body form and the plan moves both with the body.
- `read_file tests/roadmap/intake/test_roadmap_intake_agent_candidates.py 100 130` showed `tests/roadmap/intake/test_roadmap_intake_agent_candidates.py:117:candidate.title, candidate.filed_body(), labels=("source/agent",), author="NONE"`, whose assertion reads no source, so that module stays unchanged.
- `read_file docs/roadmap/refine.md 12 28` showed `docs/roadmap/refine.md:21:The Dependencies section of the body names an issue as`, which gives no rule for a parent, a related issue, a reverse link or a source line, and `read_file docs/roadmap/stage.md 24 36` showed `docs/roadmap/stage.md:30:The job leaves out an item that is not Ready, and some other items`, which points at the Dependencies section as refine reads it.
- The probe says `Not probed, the bound of 10 commands is reached` for `src/devops_cli/roadmap/intake/intake.py`, `docs/roadmap/refine.md` and `docs/roadmap/stage.md`. `read_file src/devops_cli/roadmap/intake/intake.py 215 228` showed `src/devops_cli/roadmap/intake/intake.py:227:return f"{self.body}\n\nSource: {self.source}" if self.source else self.body`, a method of `class NewCandidate:` that appends the source line to the end of the body, and `read_file src/devops_cli/roadmap/implement/implement.py 370 390` showed `src/devops_cli/roadmap/implement/implement.py:382:return open_dependency(item, self._store, self._items)`, so both modules are files of the commit and the second holds the implement job's one dependency call.
- The earlier reply named a folder in the `verify` of group 2 and named no test function in group 3. Group 2 now writes its failing test in `tests/roadmap/intake/test_roadmap_intake_evidence.py` and runs that module, and group 3 names the test function `test_a_part_is_never_a_duplicate_of_the_issue_its_source_names` and runs its module.
- The counts of the issue, 18 Ready items, 66 open items and 2 cycles, are not checked: the run called no GitHub tool.
- The related item #6450 is not checked: the run called no GitHub tool. The intake comment of the issue names it as a different change that excludes open trackers, so this plan depends on no issue.
- `body_dependencies` and `NewCandidate.filed_body` take text only: `def filed_body(self) -> str:` of `src/devops_cli/roadmap/intake/intake.py:225:def filed_body(self) -> str:` returns the string `source: str | None = None` that `src/devops_cli/roadmap/intake/intake.py:221:source: str | None = None` declares, so the tests of the plan need no checkout of the repository, no client of a service and no network; the stage test of an open dependency uses an in-memory store.
- The verify programs are `uv run devops ci test` and `uv run devops ci docs`; both come from the runner tools `uv`, `python`, `pytest`, `git` and `ruff` of the image, and no program of the plan is `NOT_IN_RUNNER`.
- Each verify command exits 0 when its row passes and 1 when one test or one docs check fails, and no verify program needs a network, a cluster or a real scanner. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.

## Existing Tool Considered

markdown-it-py (MIT, maintained, already a dependency of the repository) parses the Dependencies section into headings, paragraphs and list items; the blocker rule that it lacks costs about 50k tokens and 1.5 hours to build, keep and fix. The change deletes no internal code.

## Dependencies

None.
