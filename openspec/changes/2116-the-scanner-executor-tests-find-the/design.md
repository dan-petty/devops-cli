# Design

## Decisions

- **The fixture writes its own stand-ins on PATH, the mechanism that `ScannerFake.script` uses.** The tests of this file give the scanners `tool_executor_fake`, which starts nothing. They need only that each tool of `_REVIEW_SCANS` is findable, so that the review pipeline and the canary can name its program. The fixture keeps the old PATH after its directory, so git and the interpreter stay findable, as before.
- **The stand-in is a one-line script in the fixture.** The module `tests/support/fakes/scanners.py` keeps `_STAND_IN` private. Nothing runs the stand-in of this file. A copy costs less than a new public name in the shared fake.
- **The fixture stays autouse and local to the file.** Every test of the file needs the tools findable, and no other file shares the fixture.

## Rejected alternatives

- **Use `scanner_fake` itself.** A prototype with `scanner_fake.script(tool, ToolAnswer())` for each missing tool fails: `assert ('ran', [], False) == ('coverage_gap', [], True)`. The fixture `scanner_fake` replaces `DirectToolExecutor.run` and sets a PATH of its own, and the tests that pass `tool_executor_fake` do not expect that.
- **Keep the `shutil.which` patch.** `docs/TESTING.md` makes a patch aimed at a stdlib name a fallback for edges that have no fake. The stand-in on PATH is the established mechanism since #1982, so no exception is needed.
