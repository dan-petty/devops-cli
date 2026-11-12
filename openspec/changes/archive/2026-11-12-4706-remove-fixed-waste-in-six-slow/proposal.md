# Proposal: #4706

## Why

Six tests do work that they do not check (#4706). The CI and test audit of 2026-11-11 measured them with no coverage: the documented argv test collects the document references two times (3.73 s), the docs CLI test builds the command tree four times (5.51 s), the forage dry run crawls this repository with 40 `git log` calls (6.78 s), the teardown of `malformed_endpoint` waits out its 2.0 s join, and the memory test of the Service runs 200 rounds (13.97 s in CI). The Hypothesis property of the chunker sets `deadline=800`, which fails correct code on a loaded host.

## What Changes

- `test_every_hand_written_document_names_only_real_commands` collects the document references one time and gives them to `describe_unresolved_references`.
- `test_docs_cli_generate_and_check` keeps `generate`, `check` and `generate --check`, and no longer exports the JSON schema. `test_docs_cli_dry_run_and_format_helpers` already writes `cli_schema.json` through `generate --format json`, and now also reads the `groups` key from it.
- The forage dry run has its own test, which gives `--repo` a directory of one file. The other no-external-request commands keep the parametrized test.
- `malformed_endpoint` shuts the listener down before it closes it, so the `accept()` of its thread returns at once. The teardown waits with `THREAD_HANDOFF_BOUND_SECONDS` and fails when the thread does not end.
- The memory test of the Service runs 50 rounds with the same byte budget and slack, and its name and docstrings say 50.
- The Hypothesis property of the chunker sets no deadline, so the `ci` profile applies.
- No code under `src/` changes. The scenario "The heap after many rounds" of `github-session-answers` names the round count of the test, so the delta changes it from 200 to 50 rounds.

## Capabilities

- `github-session-answers`: the requirement "Session answers are bounded by bytes" is MODIFIED. Its text stays the same, and its scenario of the heap names 50 rounds.

## Impact

- Five of the six tests take less CI worker time. The before and after times are in a comment of the pull request.
- The docs CLI test builds the command tree three times, not four, but its time stays about the same: the argv checks of `check` and `generate --check` take most of it, and the plan keeps both paths. #4979 makes these checks faster in `src/`.
- A store with no byte bound still fails the memory test: it holds 50 answers at round 50 and 10 at round 10, a growth of 40 MiB against a slack of 6 MiB. A leak of less than about 0.15 MiB for each round can pass 40 rounds of slack.
- The change fits one pull request.

## Feasibility

- `check_documented_argv` (`src/devops_cli/docs/markdown_argv_collector.py`) is `describe_unresolved_references(collect_documented_argv_references(root))`, so the test that also needs the references can call the two parts with one collection.
- A cProfile run of `test_docs_cli_generate_and_check` at origin/main: `introspect_all_groups` ran 4 times, `check_documented_argv` 2 times (61% of the time) and `to_json_dict` 1 time (1%). `tests/invariants/test_source_tree.py` bans a patch of a devops-cli name, so the test cannot replace the argv checks of `check` and `generate --check`; both paths stay.
- `forage_cmd` (`src/devops_cli/commands/ai_research.py`) takes `--repo` and crawls only that root. In a directory that is not a git repository, its one `git rev-list` fails at once and `_git_commits_of` returns no commits.
- Linux does not wake a thread that blocks in `accept()` when another thread closes the socket. `shutdown(SHUT_RDWR)` on the listening socket makes `accept()` fail with `EINVAL`, which the thread reads as an `OSError` and returns. The baseline run at origin/main showed the thread of the fixture still in `accept()` after its test ended.
- A run of the 50-round memory test with the store of `SessionGitHubAPI` changed to a plain `dict` failed: "The heap grew 40.5 MiB between round 10 and round 50, past the 6 MiB the rest of the process may gain".
- At origin/main, a run on this host at a load average of about 60 failed `test_chunker_hypothesis_properties[py]` with `DeadlineExceeded` ("Test took 4076.22ms, which exceeds the deadline of 800.00ms"). `pyproject.toml` loads the Hypothesis `ci` profile, which has no deadline, and `docs/TESTING.md` says that a property sets no deadline of its own.

## Existing Tool Considered

The standard library (`socket.shutdown`) and the Hypothesis `ci` profile, which the suite already loads. No new tool and no new code of our own. Cost: about 30,000 tokens and 2 hours. The change deletes the second reference collection, the JSON export step of the docs CLI test and the deadline of the property.
