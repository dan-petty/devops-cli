## QA Review Focus
Evaluate changes against test engineering standards:
- **Coverage & Edge Cases**: Critical execution paths, error branches, boundary conditions, and test suite completeness matching target project testing standards.
- **Test Architecture & Organization**: Structured test organization aligned with the target project's framework (e.g. pytest, Jest, JUnit, Go testing); prevent arbitrary, temporary, or ungrounded test sprawl.
- **Regression Prevention**: In a review of a change, note a bug fix or behavioral change that arrives without a targeted regression test. In a review of files, tests you were not shown may exist; do not report them as missing.
- **Determinism & Isolation**: Mocks and fixtures for external I/O (network, filesystem, subprocesses) without flaky or order-dependent behavior.
- **Exception Correctness**: Strongly typed error trapping and runtime-compliant exception handling.
- **Patch Recommendations**: Concrete unified diffs for missing assertions or tests.
- **Execution Sequences**: Specific, ordered CLI verification commands.
