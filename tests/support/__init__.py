"""What test modules share, so none imports the root conftest or another test module (#1312).

`paths` names the repository root and its test data directories, `fakes` holds one fake per
external edge, and `waits` holds the bound a test waits with for another thread or process
(#1664). A module here is shared code, not a test: no test file lives under this package.
"""
