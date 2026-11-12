# Design

## Decisions

- The root-flag table runs through the `cli` fixture on the stub module `tests/support/dry_run_stub.py`, not on real commands. The stub `shaped` declares `--dry-run` and prints each value it gets, so one line of output shows where the resolver put the flag and that each other value arrived as typed. A real command changes when its item lands, and a run of a real command plans its requests, which is the cost that the twins had. The real-command table `test_global_dry_run_plans_the_command_it_forwards_to` stays for the shapes of real groups: an option after the subcommand, `--`, and a group with its own options.
- The stub builds its group in a function, because the gate `check_no_helper_module_under_tests_acts_on_import` refuses a statement at the top level of a helper module that does more than bind names, such as `app.add_typer(...)`.
- `refuse_requests` patches `socket.socket.connect`, `httpx2.Client.send` and `httpx2.AsyncClient.send`. It records each reach and fails at teardown, as the floor does, so a dry run whose code catches the refusal still fails. It blocks no program and no DNS lookup: the floor refuses those. A fixture that a test asks for, not an autouse one, keeps the block on dry-run tests only.
- A file whose fixtures do more than block keeps them without the block: argo keeps the DNS and cluster fakes, gh issues keeps the refusal of `gh` at the rate limiter seam, sandbox keeps the refusal of a Docker client, and pr keeps `process_fake.calls == []`.
- `misclassified` returns the commands of a table whose class is not the one expected, with the class they have, so a failure names each wrong command in one message. Seven files use it, the ones whose class tests were copies of each other. The other files keep their own class tests, which pylint symilar does not find as copies.
- The review gaps test stays. It refuses each `review` and `ai review` path in the gaps file, also a new command that has no class yet, which the ratchet allows.

## Rejected alternatives

- A unit test of `resolve_proxy_dry_run` on real commands: it checks the forwarded argv but not that the command gets it. The run through `cli` covers both, at 0.1 s for the whole table.
- Keep one per-command root case for each family: it repeats the local case, and the argv shapes of the families (positionals, options with values, `-R owner/repo`, depth 2 and 3) are all in the stub table.
- One fixture that blocks programs too: the floor refuses them at `subprocess.Popen.__init__`, beneath every seam, and a second block in a test only changes the error text.
- `tests/fixtures/dry_run_gaps.json` checks in each file: the ratchet holds criterion 2 for every reachable command.
