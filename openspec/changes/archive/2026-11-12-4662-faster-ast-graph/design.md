# Design

## Decisions
- **A substring test before the regex.** `_is_call_in_body` returns `target_name in body and re.search(...)`. The call pattern is `\b<name>\s*\(` with the name escaped, so each match holds the name as written, and a body without the name cannot match. The result is the same for every name, and the regex runs on 191 of about 3 million pairs over this repository. Most names are Markdown headings with spaces or punctuation, such as `Directory Structure`.
- **One walk that skips ignored folders.** `_walk_files` lists each folder one time with `os.scandir`. It asks the ignore index about each subfolder (`is_dir=True`) and does not go into a subfolder that git ignores. `is_ignored_by_git` also reports `.git` as ignored. Then `_collect_target_files` chooses the files by extension from that one list, and checks each candidate with `_is_excluded` as before.
- **The order of `Path.rglob`.** `--max-files` keeps the first files in the order of the walk, so the order chooses which files the graph holds. `Path.rglob` in CPython 3.14 gives the files of each subfolder of a folder in turn, then goes into the last subfolder first. The new walk keeps a stack of subfolder lists to give the same order. A folder that it does not go into held only ignored files, so the other files keep their order.
- **A folder that cannot be listed.** `Path.rglob` went past a folder that it could not list. The new walk does the same and writes a debug log line.
- **The dry-run test.** The test checks that the command makes no external request under `--dry-run`. A small folder (`--dir src/devops_cli/ai/ast`) is sufficient for that check.

## Rejected alternatives
- **One compiled pattern for each name (`functools.lru_cache`).** The issue proposes it. It gives the same result, but on the same data the link step took 4.8 s, against 0.25 s with the substring test. A module cache would also grow in the MCP server, which runs for a long time.
- **One set of call tokens for each body (`\b(\w+)\s*\(`).** It is exact only for a name that is all word characters. Over this repository, 1,550 of the 1,618 names have spaces or punctuation, so most names would still need the regex.
- **`os.walk` with pruned `dirnames`.** It gives a pre-order walk. Over this repository it found the same 4,783 Markdown files, but in a different order. Then `--max-files 100` chose other files, and the graph had 1,017 nodes and 4 edges in place of 1,889 nodes and 6 edges.
- **A walk in name order.** The output would not change between hosts, but it would choose other files under `--max-files`, and the issue asks for the same graph. A change of the file choice is a different change.
- **`git ls-files --cached --others --exclude-standard`.** It lists the files in one process, but the command also runs on a folder that is not a git repository, and the tests of the graph run with no git.
