## ADDED Requirements

### Requirement: A line citation may hold its text in the code span that follows it
The stage job SHALL read the text of a citation `path:line:` from the code span that follows it when no text stands between the citation and the next backtick. The closing backtick of the citation and white space MAY stand between them. It SHALL compare that text with the cited line as it compares the text of a citation in one span, and SHALL refuse a text of fewer than 3 characters or a text that the line does not hold.

#### Scenario: The text stands in its own span
- **WHEN** the feasibility section says `src/x.py:4:` followed by the line `def f(): pass` in a code span, and line 4 of `src/x.py` holds `def f(): pass`.
- **THEN** `check_proposal` returns no citation problem for `src/x.py`.

#### Scenario: The span holds another text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `def g(): return 1` in a code span, and line 4 of `src/x.py` holds `def f(): pass`.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.

#### Scenario: The span holds too little text
- **WHEN** the feasibility section says `src/x.py:4:` followed by `de` in a code span.
- **THEN** `check_proposal` returns a problem that names `src/x.py`.
