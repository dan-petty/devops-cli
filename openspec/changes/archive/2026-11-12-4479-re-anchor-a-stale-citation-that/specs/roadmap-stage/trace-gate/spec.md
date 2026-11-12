## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Refuse a stale line citation
The plan check SHALL refuse a `path:line:text` citation when the cited line of the staged file does not hold the cited text and no other line, or more than one other line, holds it.

#### Scenario: The line holds another text
- **WHEN** `feasibility` holds `src/sample.py:4:def g():`, line 4 of the staged `src/sample.py` holds `def f(): pass`, and no line holds `def g():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

#### Scenario: Two other lines hold the text
- **WHEN** `feasibility` holds `src/sample.py:1:def f():`, line 1 of the staged `src/sample.py` holds `import os`, and lines 4 and 7 hold `def f():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

### Requirement: Refuse a citation of an absent line
The plan check MUST refuse a citation when the reader returns no such path, or when the file holds no such line and no other line, or more than one other line, holds the cited text.

#### Scenario: The line number is past the end of the file
- **WHEN** `feasibility` holds `src/sample.py:99:def f():` and the reader returns the 11 lines of `src/sample.py`, of which lines 4 and 7 hold `def f():`.
- **THEN** `check_proposal` returns a problem that names `feasibility` and `src/sample.py`.

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
