# Design

## Context

See proposal.md for the scope (#3748, part 3 of 6 of #1335). The roadmap store seam exists already: `install_roadmap_store` and `InMemoryRoadmapStore` (#3746).

## Decisions

### 1. Each definition moves as it is
- **Decision**: a script cut each top-level definition from the old file with Python's `ast` module and wrote it unchanged into the new file. Only the imports changed (ruff sorted them and removed the unused ones), and the renamed helpers changed their name where they are used.
- **Why**: a reviewer sees pure moves. The compare of the test names before and after proves that no test is lost, and the compare of each definition with its source proves that no body changed.
- **Rejected**: rewrite the tests that still patch a `devops_cli` name. Issue #1336 owns that work, and a rewrite in the same diff hides the moves.

### 2. The files follow the behaviours of `CONTEXT.md`
- **Decision**: each new file holds the tests of one behaviour, such as the failure ledger of the run lanes or the reply of the model to intake. The name of the file states the behaviour, and so does its docstring. A test that checks a behaviour other than its neighbours moves to the file of that behaviour, even when it sat between tests of another one in the old file.
- **Why**: a failing file then says which behaviour broke. `docs/TESTING.md` asks for one file per behaviour.
- **Rejected**: cut each old file into pieces of equal size. A piece then holds two behaviours, and the next edit of the old file lands in a random piece.

### 3. Shared helpers: a support module for each old file
- **Decision**: a helper that two or more new files of one old file use goes to `tests/support/roadmap_<subject>.py`. A helper that one new file uses stays in it. A helper that a test file imports from a support module loses its underscore, and gets a new name when the short name is already in use.
- **Why**: a test file must not import another test file or a conftest, and a private name must not cross a module. Every module of `tests/support/` is a plugin, so the shared fixtures need no conftest, and an edit of a support module does not run the whole suite the way an edit of a conftest does.
- **Rejected**: `tests/roadmap/conftest.py`. The issue forbids it, and `docs/TESTING.md` says an edit of any conftest makes the narrowed run cover the whole suite.
- **Rejected**: copy the helpers into each file. That repeats the shared helpers in up to twenty files and lets the copies drift.

### 4. Shared fixtures keep their names
- **Decision**: the shared fixtures (`store`, `git_repo`, `roadmap`, `opened`, `seeded_store`, `git_sim` and the others) keep their names in the support modules.
- **Why**: a rename changes the signature of hundreds of tests, and the issue asks for pure moves. A test module that defines a fixture of the same name still overrides the plugin one, as the other refine test files do with their own `store` and `git_repo`.
- **Rejected**: prefix every shared fixture with its subject. It is a larger diff and it edits the test bodies.

### 5. Git does not show the moves as renames
- **Decision**: the proof of the move is the compare of the test names and the compare of each moved definition with its source. The change does not claim that `git diff -M -C` shows the renames.
- **Why**: git pairs two files only when they share about half of their text. A split into several files gives each new file at most a fifth of the old one.
- **Rejected**: `git mv` the old file to its largest part. It makes one new file look like a rename and the other files look new, and it hides how small the shared part is.

### 6. Two syrupy snapshots follow their tests
- **Decision**: syrupy names a snapshot file after the test module, so the two `.ambr` files move with their one test each.
- **Why**: a snapshot file named after a module that no longer exists is not read, and its test would write a new snapshot and fail on a check run.
