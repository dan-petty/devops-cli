# Proposal: #4509

## Why

The registry gate of `check_proposal` and `check_gates` reads the table of `REGISTRY_COUNTS` declarations. When the caller gives no `registry`, the gate builds the table with `registry_table(Path.cwd())`. That function runs `ast.parse` on each test module of the tree, and it keeps no result. One call takes 2 to 4 s. The implement, plan-check and plan-recheck callers and the stage gate tests give no table, so the 985 tests that get to this call use 55.6% of the junit time of a full run (#4509).

## What Changes

- `counts_in` returns no entry before `ast.parse` when the text of the module does not hold `REGISTRY_COUNTS`. A module that declares the counts assigns to that name, so its text holds it, and the table does not change. Only 7 of 1,340 test modules hold the name.
- Each call of `check_proposal`, `check_gates` and `gate_arguments` in `tests/roadmap/stage/` that does not test the registry gate passes `registry=()`. So the result of a test of another gate does not depend on the declarations of the tree. The test of a new roadmap limit, which checks a real declaration, gives the table of the checkout.

The table builder does less work for the same result. A test can see that it does not parse a module with no declaration, so the change has a spec delta.

## Capabilities

- `roadmap-stage` (modified): the table builder parses only the modules that name the registry.

## Impact

- `registry_table` on the checkout takes less than 0.2 s, and gives the same 7 entries.
- The callers that give no table (implement, plan check, plan recheck and the replay of the eval cases) get the same speed-up with no change.
- No command, setting, message or manifest changes. The change fits one pull request.

## Feasibility

- Source: `counts_in` in `src/devops_cli/roadmap/stage/stage_registry.py` reads each module and calls `ast.parse` on its text. It keeps an entry only for an `ast.Assign` or `ast.AnnAssign` at module level whose target is the name `REGISTRY_COUNTS`. So a module with an entry holds that name in its text.
- Command output at `origin/main`: `git grep -l REGISTRY_COUNTS -- tests` names 7 modules of the 1,340 `*.py` files under `tests/`, and `registry_table` gives 7 entries from 4 modules.
- Command output: on this host, at a load average of 13 to 15 on 16 CPUs, 5 calls of `registry_table` on the checkout took 3.85 s to 4.35 s each before the change.
- Python 3.14 `sys.monitoring` (PEP 669) gives a `CALL` event with the callable and its first argument. A test can see each call of `ast.parse` and its source text, and it patches nothing.

## Existing Tool Considered

The substring test of the `str` type and `functools.lru_cache` of the standard library. The change uses the substring test. A cache keyed on the path, `st_mtime_ns` and `st_size` gives 0.037 s on a warm call, but the substring test alone is fast enough, and nothing can go stale in the long-lived Service. Cost: about 60,000 tokens and 3 hours to build, and no upkeep beyond the one line. The change deletes no internal code.
