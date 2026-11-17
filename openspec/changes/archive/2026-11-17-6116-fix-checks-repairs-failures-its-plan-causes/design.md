# Design

## Decisions

- **The log names the failed files.** The step reads the files of the failed tests from the pytest summary (`FAILED <path>::<test>`, `ERROR <path>`), and the locations of the errors of ruff and mypy (`<path>:<line>: error:`, `<path>:<line>:<col>: <code>`, `--> <path>:<line>:<col>`). A traceback line of another file is not a failed file. Only a file that git tracks in the checkout is judged.
- **Four causes, in order.** For a failed file outside the plan: the branch changes the file; the file uses a name whose definition the branch changes; the file is a test that imports a module that the branch changes; the file is a snapshot test whose snapshot differs, and the branch changes a source module. The first cause that holds is the reason in the comment.
- **A changed definition.** A function, a class or a method whose `ast.dump` differs between the branch point and the head, or which only one of them holds. A dump has no line numbers, so a move is no change. A changed method also changes its class. A special method, such as `__init__`, gives only the name of its class, so `__init__` matches no caller by itself.
- **Main skew wins.** A failed file that the default branch changed after the branch point is out of scope, also when another cause holds, because a rebase repairs it and a model fix on the old head does not.
- **The read of the branch is lazy.** A log that names only paths of the plan, or no file of the checkout, needs no git call, so the round costs what it cost before.
- **The model gets the files.** `FixRequest.extra_paths` holds them. The fix group names them in code spans, and the outside-plan check of a fix step allows them. The implement job sends no extra path.
- **Tier 1 for a snapshot.** A failed syrupy assertion (`assert [+ received] == [- snapshot]`) names its test file. Tier 1 runs the snapshot update of the toolchain on those files, then `devops docs generate`, because a changed command or tool changes its snapshot and its documents, and then the tests and the docs check again. A toolchain with no snapshot command skips it.
- **One comment.** After a push, the step upserts its marked comment for the check: tier 1 names the files that it wrote, and tier 2 names the files outside the plan with their reasons.

## Rejected alternatives

- **Accept any failed file.** Main skew and an expired ignore would then get a model fix on a head that cannot repair them, and #6116 asks that they stop with a clear reason.
- **An import graph of the whole package.** The snapshot test of the MCP listing imports the server, and the server reaches the commands only through many modules. The graph needs a new dependency or a long build, and tier 1 repairs the snapshot first with no graph.
- **Treat every code span of the plan as a path.** `RepairScope` already does this, so a code span that names an identifier, such as `in_runner`, matches a log that holds the identifier. This change keeps that rule, and the failed files of the plan stay excluded from the new causes.
- **`--snapshot-file-lock`.** syrupy 7.0.2 has no such option (#5146). One process (`-n 0`) avoids the lost entries of syrupy issue 1237.
