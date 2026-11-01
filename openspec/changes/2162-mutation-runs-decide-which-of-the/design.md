# Design

## Decisions

- **Use mutmut via `uv run devops ci mutate` for mutation testing rather than building a custom mutation tool**: mutmut is already integrated in the project CI command. Building a custom tool would cost tokens to write, maintain, and fix, and would duplicate an existing maintained tool.
- **Determine a file's unique mutant by running the suite once with all tests and once with the file excluded via --ignore=**: A mutant that survives only when the file is excluded is the file's own. This is the method proposed in the issue and supported by pytest_add_cli_args_test_selection in pyproject.toml.
- **Delete a file with no unique mutant rather than keeping it behind a flag**: The project follows a pre-1.0 policy of deleting rather than keeping behind flags, as stated in ADR 0005.

## Rejected alternatives

- **Keep all 18 files and rely on line coverage alone to judge redundancy**: The issue states that line coverage alone cannot show a file is redundant because a file can cover a line and still assert something no other file asserts. The coverage audit found 84-100% overlap, not 100%.
- **Build a custom mutation testing harness in the repository**: mutmut is already integrated via `uv run devops ci mutate`. Building a custom tool would add tokens to build, keep, and fix, and would duplicate a maintained open-source tool.
