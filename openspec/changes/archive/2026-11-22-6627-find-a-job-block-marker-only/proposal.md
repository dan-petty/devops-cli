# Proposal

## Why

The job block writers and the readers find their markers with a plain text search. A person who quotes the start marker and the end marker of a block in code spans therefore loses the text between them: the alternatives check of 2026-11-21 replaced a word of the body of #6613 and put its block inside a code span, and the readers remove the same text. The change finds a marker only as an HTML block of its own, adds a block at the end when the body holds none, and keeps the person's text (#6627).

## What Changes

- `src/devops_cli/roadmap/body_hash.py` parses the body with markdown-it-py and finds a job block marker only where the marker is the whole text of an `html_block` token. A marker on the whole last line of a comment counts too.
- `extract_section_and_outside` returns the body unchanged when the start marker and the end marker are not each an HTML block, so `without_alternatives`, `text_of_a_person` and the body hash keep a quoted pair.
- `src/devops_cli/roadmap/alternatives.py` adds its block at the end of a body that holds no HTML-block marker pair, and replaces a block whose markers are each on a line of their own.
- `_marker_problem` names an unpaired marker only for an HTML-block marker, so a body that quotes both markers receives its block.
- `src/devops_cli/roadmap/refine/refine.py` reads the one marker set `JOB_BLOCK_MARKERS` from `src/devops_cli/roadmap/body_hash.py`.
- `src/devops_cli/roadmap/stage/stage_criteria.py` cuts the refine block with `extract_section_and_outside`, so a quoted marker pair stays in the criteria text.
- `close_open_block` in `src/devops_cli/roadmap/body_hash.py` closes a code fence or an HTML block that is open before a marker that a job writes. Refine and the alternatives check close their own text and the text before their block, and record the hash of the body that they write, so the next round finds one block and reads the item as unchanged.
- The tests are new in `tests/roadmap/test_roadmap_body_hash.py` and `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, and added to `tests/roadmap/test_roadmap_alternatives.py` and `tests/roadmap/stage/test_roadmap_stage_criteria.py`. `tests/roadmap/refine/test_roadmap_refine_sanitize.py` puts a blank line before the section, as refine writes it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: A marker bounds a block only as an HTML block, A check keeps its block readable after an open block, A check writes a comment, a block and a record
- `roadmap-refine/writes`: Refine keeps its section readable after an open block, The hash of the body leaves out the job's block
- `roadmap-stage/criteria`: The refine block starts and ends at an HTML block marker

## Impact

- Code: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`
- Tests: `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/refine/test_roadmap_refine_sanitize.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`

## Feasibility

- The probes report the two cited paths as files of the staging commit, word for word: "The path `src/devops_cli/roadmap/body_hash.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/alternatives.py` is a file of the staging commit." The body hash module holds `start_idx = body.find(start_marker)` at `src/devops_cli/roadmap/body_hash.py:31:start_idx = body.find(start_marker)`, and the alternatives module holds `start = body.find(CONST_ROADMAP_ALTERNATIVES_START_MARKER)` at `src/devops_cli/roadmap/alternatives.py:1096:start = body.find(CONST_ROADMAP_ALTERNATIVES_START_MARKER)`.
- The probes report the two bare names of the issue as candidates of the commit, word for word: "The path `repair.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/repair.py`. No commit in the history deleted or renamed it." and "The path `refine.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/refine/refine.py`. No commit in the history deleted or renamed it." Both files call the function that the issue names: `src/devops_cli/roadmap/repair.py` holds `_, section = extract_section_and_outside(item.body)` at `src/devops_cli/roadmap/repair.py:159:_, section = extract_section_and_outside(item.body)`, and `src/devops_cli/roadmap/refine/refine.py` holds `return token.type == "html_block" and token.content.strip() in _JOB_BLOCK_MARKERS` at `src/devops_cli/roadmap/refine/refine.py:1179:return token.type == "html_block" and token.content.strip() in _JOB_BLOCK_MARKERS`.
- Reading the body hash module showed the plain text search that the issue names: `src/devops_cli/roadmap/body_hash.py:31:start_idx = body.find(start_marker)` and `src/devops_cli/roadmap/body_hash.py:34:end_idx = body.find(end_marker, start_idx + len(start_marker))`.
- Reading the alternatives module showed the writer of the issue at `src/devops_cli/roadmap/alternatives.py:1096:start = body.find(CONST_ROADMAP_ALTERNATIVES_START_MARKER)`, the append that follows a missing block at `src/devops_cli/roadmap/alternatives.py:1095:return f"{body.rstrip()}\n\n{block}" if body.strip() else block`, and the unpaired-marker guard at `src/devops_cli/roadmap/alternatives.py:1084:if inside is None and any(marker in body for marker in markers):`.
- Reading the repair module showed the two readers of the issue, which call the function that the change fixes and need no edit of their own: `src/devops_cli/roadmap/repair.py:159:_, section = extract_section_and_outside(item.body)` and `src/devops_cli/roadmap/repair.py:209:outside, _ = extract_section_and_outside(current.body)`.
- Reading the refine module showed the rule that already exists for a section, and the append of the refine write: `src/devops_cli/roadmap/refine/refine.py:1179:return token.type == "html_block" and token.content.strip() in _JOB_BLOCK_MARKERS` and `src/devops_cli/roadmap/refine/refine.py:3724:new_body = outside.rstrip() + "\n\n" + rendered_section`.
- Reading the refine module showed that markdown-it-py is already in use for a body: `src/devops_cli/roadmap/refine/refine.py:1238:section = _section_tokens(MarkdownIt("commonmark").parse(persons_text), _KEY_QUESTIONS_TITLE_RE)`.
- Reading the store module showed that the repository already reads the token type and the line map of a body: `src/devops_cli/roadmap/stores/store.py:921:_BODY_MARKDOWN: Final = MarkdownIt("commonmark").disable("inline")`, `src/devops_cli/roadmap/stores/store.py:951:last = next((token for token in reversed(_BODY_MARKDOWN.parse(body)) if token.level == 0), None)` and `src/devops_cli/roadmap/stores/store.py:952:if last is None or last.type != "html_block" or last.map is None:`.
- The marker set that the change moves is defined at `src/devops_cli/roadmap/refine/refine.py:1163:_JOB_BLOCK_MARKERS: Final[frozenset[str]] = frozenset(`.
- The `references` call for `_JOB_BLOCK_MARKERS` answered 3 files and 6 lines: 2 lines of the refine module, at `src/devops_cli/roadmap/refine/refine.py:1163:_JOB_BLOCK_MARKERS: Final[frozenset[str]] = frozenset(` and `src/devops_cli/roadmap/refine/refine.py:1179:return token.type == "html_block" and token.content.strip() in _JOB_BLOCK_MARKERS`, and 3 lines of two files under `openspec/changes/archive/`. Group 2 changes the refine module, and the archive files stay as history.
- The staged constants that the plan relies on: `src/devops_cli/config/constants.py:3480:CONST_ROADMAP_REFINE_START_MARKER: Final[str] = "<!-- devops-roadmap-refine:start -->"` and `src/devops_cli/config/constants.py:3695:CONST_ROADMAP_ALTERNATIVES_START_MARKER: Final[str] = "<!-- devops-roadmap-alternatives:start -->"`. The plan relies also on `CONST_ROADMAP_REFINE_END_MARKER` and `CONST_ROADMAP_ALTERNATIVES_END_MARKER`, and their values are not checked.
- A search for `CONST_ROADMAP_REFINE_START_MARKER` showed one more reader that the expected behavior of the issue covers: `src/devops_cli/roadmap/stage/stage_criteria.py:118:start = body.find(CONST_ROADMAP_REFINE_START_MARKER)`, under `src/devops_cli/roadmap/stage/stage_criteria.py:117:def _without_refine_block(`.
- The review finding on group 4 is corrected and not refuted: `src/devops_cli/roadmap/stage/stage_criteria.py:226:if not acceptance_level:` leaves every item of the acceptance-criteria list out of `requirement_lines`, so the group test gives the criterion between the quoted markers to `acceptance_criteria`, and reads a bullet that names a path, outside that list, as a requirement line.
- The read of #6613 and PR #6624 showed that the merged #6624 ended a body section at a marker only where the marker is an HTML block, at `src/devops_cli/roadmap/refine/refine.py:1179:return token.type == "html_block" and token.content.strip() in _JOB_BLOCK_MARKERS`, and that it changed no marker search, so this change builds on it and repeats none of it.
- The version of markdown-it-py that `uv.lock` pins is not checked; the change relies only on the `html_block` token and its line map, which the store module already reads.
- The plan calls no function whose arguments need a checkout, a client or a network: `MarkdownIt("commonmark").parse` reads a body string, and each test doubles no process edge and reaches no network, no cluster and no real scanner.
- The stage replay keeps its score: group 4 runs `uv run devops roadmap eval stage --replay` and compares the score before the change with the score after it, and a moved score stops the group.
- Each verify command is `uv run devops ci test` with `pytest`, and both are listed under Runner capabilities Image tools; the pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`, and a failed verify is the failure class `test`, whose action is `repair`.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/roadmap/test_roadmap_body_hash.py`, `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` and `uv run devops roadmap eval stage --replay`.
- No test module of its own covers the body hash module at the staged commit: the probes list the test modules that call `extract_section_and_outside`, among them the alternatives and refine test modules, so the plan creates a new test module in the folder under `tests/` that mirrors the package of the code it tests.

## Existing Tool Considered

markdown-it-py (https://pypi.org/project/markdown-it-py), MIT License, maintained, and already in use: the refine module and the store module import `MarkdownIt`, so the change adds only the project's marker set and the splice and append logic.

## Dependencies

None.
