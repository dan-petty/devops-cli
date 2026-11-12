## MODIFIED Requirements

### Requirement: A plan number beside a constant matches the staged value
The plan check SHALL refuse a plan when a sentence names one known module-level integer constant of the staged tree, holds one candidate decimal number, gives that number to the constant, and that number differs from the value of the constant. A sentence gives a number to a constant when the number follows the constant name with `=`, `is` or `to`, as in `SUMMARY_MAX_CHARS = 40`, `SUMMARY_MAX_CHARS: Final[int] = 40`, `SUMMARY_MAX_CHARS` is 40, and sets `SUMMARY_MAX_CHARS` to 40. A candidate number is a whole number: the digits of a range such as `1790-2000` give no candidate number.

#### Scenario: Summary bound mismatch
- **WHEN** A spec scenario says `SUMMARY_MAX_CHARS` is 40, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns one problem that names `SUMMARY_MAX_CHARS`, 40 and 60.

#### Scenario: An assignment in a code span
- **WHEN** A design decision quotes `SUMMARY_MAX_CHARS: Final[int] = 40`, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns one problem that names `SUMMARY_MAX_CHARS`, 40 and 60.

#### Scenario: Summary bound match
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 60, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A bound after the constant name
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` holds 60 characters, and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: A note reference beside the constant
- **WHEN** A requirement says `SUMMARY_MAX_CHARS` is 60 (#2714), and the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Two numbers in one sentence
- **WHEN** A design decision says `SUMMARY_MAX_CHARS` is 40, while the staged tree sets it to 60.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the sentence is ambiguous.

#### Scenario: A line range beside the constant
- **WHEN** A feasibility line says that `read_file` of `ci.py` lines 1790-2000 showed `ci.py:1830:if len(targets) <= DEFAULT_CI_TEST_SERIAL_MAX_FILES:`, and the staged tree sets `DEFAULT_CI_TEST_SERIAL_MAX_FILES = 12`.
- **THEN** The check returns no problem about `DEFAULT_CI_TEST_SERIAL_MAX_FILES`.

#### Scenario: A number that is no value of the constant
- **WHEN** A sentence holds `DEFAULT_CI_TEST_SERIAL_MAX_FILES + 1`, or runs pytest with `-n 0` and with `-n DEFAULT_CI_TEST_NARROWED_WORKERS`, or adds `DEFAULT_CI_TEST_SERIAL_MAX_TESTS: Final[int] = 50` after `DEFAULT_CI_TEST_NARROWED_WORKERS`, or edits line 266 that names `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS`, and the staged tree defines the named constant with another value.
- **THEN** The check returns no problem about the constant, because the sentence gives the number to no constant that the tree defines.
