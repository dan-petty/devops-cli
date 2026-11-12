# Proposal: #4662

## Why
`devops ai ast graph` was slow, and its dry-run test took 15.06 s in CI (#4662). Two parts of the build caused this:

- The link step ran `re.search` with a new pattern for each pair of a symbol body and a name. There were about 3 million pairs over this repository. The pattern changed at each call, so each call missed the `re` cache and compiled the pattern again.
- The file walk ran `Path.rglob` one time for each of the 32 extensions and 2 container file names. Each walk went into `.venv`, `.git` and the other folders that git ignores, and dropped their files only after it found them.

The dry-run test ran the command on the whole repository, but it checks only the exit code.

## What Changes
- The link step searches a body for the call pattern of a name only when the body holds that name. The pattern holds the name as written, so a body without the name cannot match. Only 191 of the pairs over this repository get to the regex.
- The file walk lists the tree one time with `os.scandir` and does not go into `.git` or a folder that git ignores. It keeps the order of `Path.rglob`, so `--max-files` chooses the same files. The graph of this repository has the same files, nodes and edges as before.
- The dry-run test of `ai ast graph` builds the graph of `src/devops_cli/ai/ast` with `--dir`, not of the whole repository.
- A spec delta adds the walk rule to `ast-support`: the command does not list an ignored folder. The change is observable as time and as the folders that the command reads.

The change fits one pull request.

## Capabilities
- `ast-support`: ADDED requirement "The code graph walk skips each ignored folder".

## Impact
- `src/devops_cli/ai/ast/graph.py`: the walk and the call test.
- `tests/ai/ast/test_treesitter_engine.py`: two new tests.
- `tests/commands/test_ai_local_dry_run.py`: the dry-run case runs on a small folder.
- No new dependency. The output of the command does not change.

## Feasibility
Confirmed on this repository with CPython 3.14.10, in one process, the old `graph.py` from `origin/main` beside the new one:

- The old and the new build give the same hash of files, nodes and edges: 100 files, 1,889 nodes and 6 edges.
- At load average 10, the old build took 159 s and the new build took 8.8 s. The old file walk took 10.8 s and the new one took 4.8 s.
- In the link step, the substring test sends 191 pairs to the regex, and the step takes 0.25 s. One compiled pattern for each name (`functools.lru_cache`) took 4.8 s on the same data.
- The source of `glob._GlobberBase.recursive_selector` in CPython 3.14 gives the order of `Path.rglob`: the files of each subfolder of a folder, then the last subfolder first. The new walk gives the same order. The project requires Python 3.14 or later.
- The ignore index of `devops_cli.core.gitignore` stops at the first ignored folder of a path, so a file under an ignored folder is always ignored. A walk that does not go into an ignored folder finds the same files.

## Existing Tool Considered
The standard library: `os.scandir` for the walk and `re` for the call test, with the ignore index that the project already has. `os.walk` gives a pre-order walk, which chooses different files under `--max-files`. `git ls-files` would start a process, and the command also runs on a folder that is not a git repository. No code is deleted except the per-extension `rglob` loops. Cost to build: about 40,000 tokens and 1 hour.
