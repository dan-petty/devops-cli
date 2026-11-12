## MODIFIED Requirements

### Requirement: The context lists the tests and the callers of a cited symbol
The context that the stage and refine jobs give the model SHALL hold, for up to five identifiers that the item cites in backticks, the source files of the checked-out commit that name each one as a whole word, Markdown files excepted. It SHALL name the file and line of up to three definitions, then the test files, then the callers. A test file is under `tests/` or named `test_*.py` or `*_test.py`; every other file is a caller. An identifier that no file names SHALL add no section.

#### Scenario: A cited symbol is named by tests and by source files
- **WHEN** an item cites `hello_world`, and `tests/test_sample.py`, `pkg/test_inline.py` and `pkg/inline_test.py` name it, and `src/caller.py`, `src/contest.py` and `src/sample.py` name it
- **THEN** the context holds the section "Tests and callers of `hello_world`", the three test files under "Tests:" and the three source files under "Callers:"

#### Scenario: A cited Rust function
- **WHEN** an item cites `explorer_patrol_system`, which `src/game/unit.rs` defines on line 5 and calls, and `tests/patrol.rs` calls it
- **THEN** the section of `explorer_patrol_system` holds "Defined at: src/game/unit.rs:5", `tests/patrol.rs` under "Tests:" and `src/game/unit.rs` under "Callers:"

#### Scenario: A cited symbol that no file names
- **WHEN** an item cites `missing_symbol` and no source file names it
- **THEN** the context holds no section "Tests and callers"
