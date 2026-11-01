# Design

## Decisions

- **Rewrite tests to call the public CLI command via the cli fixture instead of importing and calling private functions directly**: ADR 0007 and docs/TESTING.md require tests to use public interfaces over shared fakes. The cli fixture pattern already exists in tests/commands/test_pr.py and is the established target pattern.
- **Replace MagicMock instances with shared fakes from tests/support/fakes/**: The acceptance criteria state each double must be a shared fake from tests/support/fakes/ installed through its seam or fixture. MagicMock is an inline double that bypasses the shared fake contract.
- **Remove private product code that exists only to be patched by a test**: #1307 Q27 specifies that product code needed only for a patch goes. Keeping dead private code adds maintenance cost without consumer value.
- **Group the 49 files into 21 steps by domain**: Each step must fit the 40000-token budget with its files. Grouping by domain keeps related changes together and makes each step self-contained.
- **Provide a spec delta for the test-public-interface capability**: The change removes private product code and alters the test suite's coupling to internals. The validator requires a spec delta when product code is removed, even if the code is private.

## Rejected alternatives

- **Make all private functions public by removing the underscore prefix**: This would expose internal implementation details as a public API, violating the encapsulation that the underscore prefix signals. The acceptance criteria require tests to use the public CLI interface, not a widened module API.
- **Keep the patch sites and add a lint rule to suppress the warning**: The acceptance criteria explicitly require zero patch sites and zero private imports. A lint suppression does not remove the coupling; it hides it. ADR 0007 requires the coupling to be removed, not suppressed.
- **Split the 49 files across multiple pull requests**: The issue states this item is one child of #1307 for the files that no other child names. The acceptance criteria require all 49 files to be clean in one pull request. Splitting would leave files in a mixed state.
