# roadmap-stage/trace-gate Specification

## Purpose
The trace gate of a plan: each line, symbol and path citation of the evidence fields agrees with the file text at the staged commit or with the tool calls of the plan run.

## Requirements

### Requirement: Refuse a stale line citation
The plan check SHALL refuse a `path:line:text` citation when the cited line of the staged file does not hold the cited text and no other line, or more than one other line, holds it.

#### Scenario: The line holds another text
- **WHEN** `feasibility` holds `src/sample.py:4:def g():`, line 4 of the staged `src/sample.py` holds `def f(): pass`, and no line holds `def g():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

#### Scenario: Two other lines hold the text
- **WHEN** `feasibility` holds `src/sample.py:1:def f():`, line 1 of the staged `src/sample.py` holds `import os`, and lines 4 and 7 hold `def f():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Accept a true line citation
The plan check SHALL accept a `path:line:text` citation when the cited line of the staged file holds the cited text.

#### Scenario: The line holds the cited text
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 of the staged `src/sample.py` holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse a citation of an absent line
The plan check MUST refuse a citation when the reader returns no such path, or when the file holds no such line and no other line, or more than one other line, holds the cited text.

#### Scenario: The line number is past the end of the file
- **WHEN** `feasibility` holds `src/sample.py:99:def f():` and the reader returns the 11 lines of `src/sample.py`, of which lines 4 and 7 hold `def f():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Resolve a symbol citation
The plan check SHALL accept a `path:def name` or a `path:class name` citation when the staged file defines the symbol at any line.

#### Scenario: The definition moved
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines `def f(` at line 7.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: Refuse an absent symbol
The plan check MUST refuse a symbol citation when the staged file holds no definition of the symbol.

#### Scenario: The file defines another symbol
- **WHEN** `feasibility` holds `src/sample.py:def f` and the staged `src/sample.py` defines only `def g(`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Scan the three evidence fields
The plan check SHALL scan `feasibility`, `why` and each line of `what_changes` for citations.

#### Scenario: A stale citation sits in what_changes
- **WHEN** a line of `what_changes` holds a citation of a line that holds other text.
- **THEN** `check_proposal` returns a problem that names `what_changes` and the cited path.

### Requirement: Judge no citation without file text
The plan check SHALL judge no citation when it holds no reader of the staged files.

#### Scenario: The check holds no reader
- **WHEN** `check_proposal` runs with no `read_text` callable and the plan holds a stale citation.
- **THEN** `check_proposal` returns no problem for that citation.

### Requirement: Compare a citation with collapsed white space
The plan check SHALL compare the cited text with the staged line after it collapses white space in both.

#### Scenario: The spacing differs
- **WHEN** `feasibility` holds `src/sample.py:4:def f():` and line 4 holds `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

### Requirement: The stage job reads the text of a cited file at the staged commit
The stage job SHALL pass `check_proposal` a reader that returns the text of a cited file at the staged commit, and the replay MUST pass no reader.

#### Scenario: The job holds the checkout and the commit
- **WHEN** the stage job holds the checkout and the staged commit, and a plan cites `src/sample.py`, and the reader is asked for its text.
- **THEN** the reply holds the lines of `src/sample.py` at that commit.

#### Scenario: The replay passes no reader
- **WHEN** the replay of the golden set calls `check_proposal` with no reader, and a plan cites `src/sample.py`.
- **THEN** the check judges no citation.

### Requirement: The stage prompt prefers a symbol citation
The stage prompt MUST tell the planner to cite a symbol instead of a line number when a line is not needed.

#### Scenario: The prompt states the symbol form
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** the text holds the `path:def name` form and the instruction to prefer it.

### Requirement: Feasibility cites only what the plan run did
The stage job SHALL refuse a feasibility line that names a toolbox tool, or states that a code-span path was read, when the plan runs of the item hold no call that supports it, and SHALL accept a line that negates the claim.

#### Scenario: A read claim with no tool call
- **WHEN** The trace holds zero calls and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns a problem that names `src/x.py` and the absent read.

#### Scenario: A read claim that the trace supports
- **WHEN** The trace holds a `read_file` call for `src/x.py` and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A tool name that the trace lacks
- **WHEN** The trace holds no `search_code` call and the feasibility section says `search_code` returned a result.
- **THEN** `check_proposal` returns a problem that names `search_code`.

#### Scenario: A stated gap
- **WHEN** The trace holds zero calls and the feasibility section says `not read `src/x.py``.
- **THEN** `check_proposal` returns no problem for that line.

#### Scenario: A caller with no run
- **WHEN** `check_proposal` gets no trace facts and the feasibility section says `read `src/x.py``.
- **THEN** `check_proposal` returns no trace problem, and its other checks run as before.

#### Scenario: A claim of the first run after a return
- **WHEN** The first plan run called `read_file` for `src/x.py`, its reply was returned for another problem, the second plan run called no tool, and the second reply says `read `src/x.py``.
- **THEN** The second reply passes the trace gate.

### Requirement: Trace facts of a run
`TraceFacts.of` SHALL hold the tool name of each call of a `RunTrace` and the `path`, `directory` and `paths` values of an argument that parses as JSON, and the stage job SHALL pass to `check_proposal` the facts of the combined trace of every plan run of the item so far. A review run SHALL NOT be a plan run.

#### Scenario: A trace with two calls
- **WHEN** The trace holds a `read_file` call for `src/x.py` and a `search_code` call for `needle`.
- **THEN** The facts hold the tools `read_file` and `search_code`, and the path `src/x.py`.

#### Scenario: The stage job calls the check
- **WHEN** The planner gets a reply from a toolbox run that called `read_file` for `src/x.py`.
- **THEN** The `check_proposal` call for that reply holds the facts with the tool `read_file` and the path `src/x.py`.

#### Scenario: The facts hold every plan run
- **WHEN** The first plan run called `read_file` for `src/x.py` and the second plan run called no tool.
- **THEN** The facts hold the tool `read_file` and the path `src/x.py`.

#### Scenario: A review run supports no claim
- **WHEN** A review run called `read_file` for `src/x.py` and no plan run called it.
- **THEN** The facts hold no tool and no path.

### Requirement: The planner prompt cites only the run
The planner prompt and `docs/roadmap/stage.md` SHALL state that a plan cites only the tools and the paths that its run used, and that a premise that the run did not check is written as `not checked`.

#### Scenario: The prompt rule is present
- **WHEN** The stage prompt and `docs/roadmap/stage.md` are read.
- **THEN** Both hold the same sentence of the rule, and the tests in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` pass.

### Requirement: A line citation may hold its text in the code span that follows it
The stage job SHALL read the text of a citation `path:line:` from the code span that follows it when no text stands between the citation and the next backtick. The closing backtick of the citation and white space MAY stand between them. It SHALL judge that text as it judges the text of a citation in one span, and SHALL refuse a text of fewer than 3 characters or a text that the line does not hold and that not exactly one other line holds.

#### Scenario: The text stands in its own span
- **WHEN** the feasibility section says `src/x.py:4:` followed by the line `def f(): pass` in a code span, and line 4 of `src/x.py` holds `def f(): pass`.
- **THEN** `check_proposal` returns no citation problem for `src/x.py`.

#### Scenario: The span holds another text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `def h(): return 2` in a code span, line 4 of `src/x.py` holds `def f(): pass`, and no line holds `def h(): return 2`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

#### Scenario: The span holds too little text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `de` in a code span.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

### Requirement: Code that reads a file is no claim of the run
The stage job SHALL NOT take `reads` or `reading` as a claim that the run read a path when a code span, `it` or `which` is its subject. It SHALL still refuse a claim of the run or of the author, such as `I read` or `the run read`, when the plan runs hold no call for the path.

#### Scenario: A function reads a file
- **WHEN** the trace holds no call and the feasibility section says `because it reads `.github/labels.yml` of the default branch`.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: The author reads a file
- **WHEN** the trace holds no call and the feasibility section says `I read `src/x.py` and found the function`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

### Requirement: The trace gate reads the path of each citation form
The stage job SHALL judge a Feasibility read claim by the path of its code span: the path of a `path:N`, `path:N-M`, `path:N:text` or `path:def name` citation, without a toolbox tool name before it, a leading `./` or a trailing `/`. It SHALL remove each sentence of the probe lines that the plan quotes before it reads the claim. It SHALL still refuse a claim of a path that the plan runs did not read, and name that path.

#### Scenario: A line range of a read file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/x.py:10-20``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A tool name before a read path
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `read_file src/x.py``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A listed directory with a trailing slash
- **WHEN** the trace holds a `list_files` call for the directory `tests/telemetry` and the feasibility section says `the run read `tests/telemetry/``.
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A line range of an unread file
- **WHEN** the trace holds a `read_file` call for `src/x.py` and the feasibility section says `the run read `src/y.py:10-20``.
- **THEN** `check_proposal` returns a problem that names `src/y.py`.

#### Scenario: A quoted probe line
- **WHEN** the trace holds no call, the probe lines hold `The path `src/x.py` is a file of the staging commit.`, and the feasibility section says `The probe line reads: The path `src/x.py` is a file of the staging commit.`
- **THEN** `check_proposal` returns no trace problem.

### Requirement: The trace gate reads the subject and the object of a read word
The stage job SHALL take a read word as a claim of the run only when it is `read_file`, a passive or participle, a noun read, a read with no subject, or a read whose subject or list subject names the run or its author. A subject that is the plan, a group, the probe or code, and `read-only` SHALL be no claim. The gate SHALL judge the path that the read takes: the subject of a passive, else the first path of its object up to a result verb unless a pronoun starts it, else the last path before it.

#### Scenario: The plan is the subject
- **WHEN** the trace holds no path and the feasibility section says `` This plan reads `tests/x.py` in group 2. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A read-only root
- **WHEN** the trace holds no path and the feasibility section says `` `k8s/x.yaml` runs the pod with a read-only root. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A path in another clause
- **WHEN** the trace holds the tools `read_file` and `search_code` and no path, and the feasibility section says `` `read_file` of that prompt shows the rule, and `search_code` returned one hit in `src/tf.py`. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A path in the result of a read
- **WHEN** the trace holds the tool `read_file` and the path `docs/a.md`, and the feasibility section says `` `docs/a.md` is a file, and `read_file` on it showed the text "see `src/b.py`". ``
- **THEN** `check_proposal` returns no trace problem, and with only the path `src/b.py` in the trace it returns a problem that names `docs/a.md`.

#### Scenario: A claim of the run
- **WHEN** the trace holds no path and the feasibility section says `` I read `src/missing.py` and found the function. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A passive read
- **WHEN** the trace holds no path and the feasibility section says `` `src/missing.py` was read on the base. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A verb of a list
- **WHEN** the trace holds no path and the feasibility section says `` I listed the folder, opened the test and read `src/missing.py`. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A noun read
- **WHEN** the trace holds no path and the feasibility section says `` A quick read of `src/missing.py` shows the seam. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A participle
- **WHEN** the trace holds no path and the feasibility section says `` The file `src/missing.py`, read at the base, shows the seam. ``
- **THEN** `check_proposal` returns a problem that names `src/missing.py`.

#### Scenario: A pronoun object
- **WHEN** the trace holds the tool `read_file` and the path `docs/a.md`, and the feasibility section says `` `docs/a.md` is a file, and `read_file` on it revealed the text "see `src/b.py`". ``
- **THEN** `check_proposal` returns no trace problem, and with only the path `src/b.py` in the trace it returns a problem that names `docs/a.md`.

### Requirement: A search match supports a citation of its line
`TraceFacts.of` SHALL hold the `path:line` of each match line of a `search_code` or `callers` answer, and the kept plan file SHALL hold those that its Feasibility section cites. The trace gate SHALL accept a read whose object is a `path:line` or `path:line:text` citation of such a line. It SHALL still refuse `read_file`, a read that takes the line through a pronoun, a claim of the whole file, of another line or of a line range, and it SHALL give a path of a probe line no support.

#### Scenario: A search answer
- **WHEN** a `search_code` call of a plan run gets the answer `tests/a.py:5:import x`
- **THEN** `TraceFacts.of` holds the line `tests/a.py:5`.

#### Scenario: A citation of a match line
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` The run read `tests/a.py:5:import x`. ``
- **THEN** `check_proposal` returns no trace problem.

#### Scenario: A claim of the whole file
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` The run read `tests/a.py`. ``
- **THEN** `check_proposal` returns a problem that names `tests/a.py`.

#### Scenario: A pronoun read of a match line
- **WHEN** the trace holds the match line `tests/a.py:5` and no path, and the feasibility section says `` `search_code` returned `tests/a.py:5:import x`, and `read_file` on it showed the imports. ``
- **THEN** `check_proposal` returns a problem that names `tests/a.py`.

### Requirement: The trace gate reads the path of a tool call citation
The Feasibility trace gate SHALL take the first quoted argument of a call to a stage tool, such as `read_file("src/a.py", 60, 80)`, as the claimed path, with double or single quotes. It SHALL apply the rules of the `path:line` form and of a leading `./` to it. A call of a word that is no stage tool SHALL stay whole.

#### Scenario: A double-quoted call of a read path
- **WHEN** a Feasibility line cites `read_file("src/devops_cli/sample.py", 60, 80)` and the trace holds `read_file` and that path
- **THEN** `check_proposal` returns no trace-path problem

#### Scenario: A single-quoted call of a read path
- **WHEN** a Feasibility line cites `read_file('src/devops_cli/sample.py', 60, 80)` and the trace holds `read_file` and that path
- **THEN** `check_proposal` returns no trace-path problem

#### Scenario: A call of an unread path
- **WHEN** a Feasibility line cites `read_file("src/devops_cli/other.py", 60, 80)` and the trace holds no such path
- **THEN** `check_proposal` returns one problem that names `src/devops_cli/other.py`

#### Scenario: A call of a word that is no stage tool
- **WHEN** a Feasibility line cites `cat("src/devops_cli/sample.py")`
- **THEN** the claimed path is the whole span and the gate refuses it

#### Scenario: The space form keeps its result
- **WHEN** a Feasibility line cites `read_file src/devops_cli/sample.py` and the trace holds that path
- **THEN** `check_proposal` returns no trace-path problem

### Requirement: Re-anchor a stale line citation whose text is on one other line
The plan check SHALL accept a `path:line:text` citation as a citation of another line when the cited line of the staged file does not hold the cited text, or the file holds no such line, and exactly one other line holds the text. It SHALL compare each line as it compares the cited line, SHALL refuse a text of fewer than 3 characters before it looks at other lines, and SHALL not re-anchor a citation whose cited line holds the text.

#### Scenario: One other line holds the text
- **WHEN** `feasibility` holds `src/sample.py:4:return 1`, line 4 of the staged `src/sample.py` holds `def f(): pass`, and only line 8 holds `return 1`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

#### Scenario: One other line holds the text in a longer line
- **WHEN** `feasibility` holds `src/sample.py:4:return`, and only line 8 of the staged `src/sample.py` holds `return 1`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`.

#### Scenario: The cited line and another line hold the text
- **WHEN** `feasibility` holds `src/sample.py:7:def f():`, and lines 4 and 7 of the staged `src/sample.py` hold `def f():`.
- **THEN** `check_proposal` returns no problem that names `src/sample.py`, and the log line counts no re-anchored citation.

#### Scenario: A short text on one other line
- **WHEN** `feasibility` holds `src/sample.py:4:G:`, and only line 10 of the staged `src/sample.py` holds `G:`.
- **THEN** `check_proposal` returns the problem of a citation with fewer than 3 characters, and the log line counts no re-anchored citation.

### Requirement: Log the count of re-anchored line citations
The plan check SHALL write one log line, `The citation gate re-anchored <n> of <m> line citations.`, each time it judges the citations of a plan with a reader of the staged files: `<n>` is the number of line citations that it re-anchored to another line, and `<m>` is the number of line citations of the plan. A check with no reader SHALL write no such line.

#### Scenario: Two citations are re-anchored
- **WHEN** `feasibility` holds two line citations whose texts are each on exactly one other line of their staged file.
- **THEN** the log holds one line `The citation gate re-anchored 2 of 2 line citations.`

#### Scenario: The check holds no reader
- **WHEN** `check_proposal` runs with no `read_text` callable and the plan holds a stale line citation.
- **THEN** the log holds no line that starts with `The citation gate re-anchored`.
