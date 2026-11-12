# Proposal: #4731

## Why

The dry-run tests repeat work that other tests already do (#4731):

- 40 cases of `test_request_plan_flag_order_global_dry_run` run each request-plan command again under the root `--dry-run`. Argo, Cloudflare, Valkey and Vault, pr, scan and the three gh files do the same inside their run tests. Only the generic resolver lines of the root flag differ from the local case.
- 14 tests check that the commands of their class table are not in `tests/fixtures/dry_run_gaps.json`. The ratchet `tests/invariants/test_dry_run_class_ratchet.py` already fails a classified command in that file, and the class test of each file fails a command that loses its class.
- 19 dry-run files block subprocesses, DNS or external connects, which the floor of the suite already refuses (`tests/conftest.py`), each with its own copy of the block.
- The dry-run test family has 3.70% duplicate lines (pylint symilar, `-d 8`), 4.24% on the base of this change.

## What Changes

- `tests/commands/test_global_dry_run.py` tests the root `--dry-run` on a table of argv shapes through a stub command that declares `--dry-run`: no argument, positionals, an option with a value (long, short, `=`), an option value that is `--dry-run`, a flag, `--`, a nested group and a flag that is given twice. The per-command twins go.
- The gaps tests whose list is within their class table go. The prefix rule of the review commands stays.
- `tests/support/dry_run_requests.py` gives one fixture, `refuse_requests`, the network block of dry runs: it refuses and records each socket connect and each httpx2 request, also one that a fake would answer. The subprocess, DNS and per-file network blocks go.
- `tests/support/dry_run_classes.py` gives `misclassified`, which the class tests of seven files use in place of their own loops.
- `docs/TESTING.md` says how a dry-run test uses the floor, the two helpers, the ratchet and the root-flag table.

No behavior of a command changes, so the change has no spec delta (`skip_specs: true`).

## Capabilities

None. The change edits tests and one test document only.

## Impact

- The family has 557 tests in place of 662. On 4 pinned CPUs it takes 108.7 s of CPU in place of 142.8 s, and 34.1 s of wall time in place of 42.9 s (mean of 3 interleaved runs).
- The duplicate share of the family is 0.58% (32 of 5,528 lines).
- The change fits one pull request.

## Feasibility

- The floor refuses each program but git, offline kubectl renderers and live tools at `subprocess.Popen.__init__`, each connect to a host that is not loopback, each unowned loopback connect and each DNS query that needs a name server, and records each reach so that a test fails also when the code caught the refusal (`tests/conftest.py`, `refuse_real_programs`, `prevent_external_network_calls`, `unexpected_loopback_connects`).
- Criterion 2 of the ratchet fails a classified command that stays in the gaps file. A one-time check resolved each name of the 14 gaps lists to its Click command and found its callback in the class table of the same file: 14 of 14 lists, no name outside.
- `resolve_proxy_dry_run` (`src/devops_cli/core/command_resolver.py`) inserts `--dry-run` after the command path from the parse of Click, so the argv of a stub shows each shape. Three mutations of it each fail the new table: `--dry-run` at the end of argv (the `--` case), at a fixed depth (the nested group case), and a token scan in place of the parsed value (the option value and `--` cases).
- `pylint symilar 4.0.2 -d 8` over `tests/commands/*dry_run*.py` and `tests/github/*dry_run*.py` gives the duplicate share.

## Existing Tool Considered

pytest fixtures and `parametrize` carry the shared block and the table, and pylint symilar measures the duplicate share. No new tool is needed. The change deletes the per-file guard fixtures, the inline subprocess and socket blocks, the 14 gaps tests, the per-command root twins and the per-command class tests of seven files.
