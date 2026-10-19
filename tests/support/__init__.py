"""What test modules share, so none imports the root conftest or another test module (#1312).

`paths` names the repository root and its test data directories, and `fakes` holds one fake per
external edge. A module here is shared code, not a test: no test file lives under this package.
"""
