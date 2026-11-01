### What happened

Two accommodations for tests reached the code after #1309 and #1332 were filed, and no check stopped them:

- `security/ruff.py:23` imports `run_subprocess` with `# noqa: F401`. The module does not use the name, and no test at b170358e patches it. The other scanner modules keep the same import as a patch target. It came with v0.2.33 (#1537, 2026-10-10). #1332 names the re-imports of seven scanner modules, and not this one.
- `core/process.py:401` keeps `_prepare_cmd = prepare_tool_cmd`, a private alias of a public function. `tests/support/fakes/process.py:20` imports the private alias, and `tests/test_process.py:544-559` tests it. The shared fake reaches a private name, which docs/TESTING.md does not allow.

#1309 decided not to count `# noqa: F401` patch-target re-imports, because "they have no reason to come back once the patches they serve are gone" (#1309, key questions). The re-import in `security/ruff.py` came after that decision, while the other 14 still stand. So the kind needs a check.

### What should happen

- The re-import in `security/ruff.py` goes.
- The alias `_prepare_cmd` goes. The fake and `tests/test_process.py` use `prepare_tool_cmd`.
- A check fails when `src/` gains a `# noqa: F401` import that the module does not use. `ruff check --select F401 --ignore-noqa src` finds such imports: at b170358e it reports 15, all in `security/` (`bandit.py:17`, `gitleaks.py:17`, `:19`, `kubelinter.py:15`, `:16`, `pluto.py:14`, `:15`, `popeye.py:11`, `:12`, `ruff.py:23`, `semgrep.py:23`, `:24`, `tflint.py:6`, `:12`, `:13`). The check holds the count at the sites that #1332 removes, and allows no new one.

### Evidence

At b170358e:
- `src/devops_cli/security/ruff.py:23`.
- `src/devops_cli/core/process.py:401`; `tests/support/fakes/process.py:20`, `:123`, `:191`; `tests/test_process.py:544-559`.
- `uv run ruff check --select F401 --ignore-noqa src`: 15 findings.

### Acceptance criteria

- [ ] `src/devops_cli/security/ruff.py` imports no name it does not use, and its tests patch no `devops_cli` name.
- [ ] `rg -n "_prepare_cmd" src tests` prints nothing.
- [ ] A `devops ci` row runs `ruff check --select F401 --ignore-noqa` over `src/` and fails on a new site. The pull request shows it failing on an added re-import. The ceiling is the count of the sites #1332 owns, and it goes to zero with #1332.
- [ ] The row runs on the stock runner with no install, and its job stays under 5 minutes.
- [ ] `uv run devops ci` passes.

Related: #1309 (the ratchets; this item adds the kind it left out, and does not change #1309), #1332 (owns the other 14 re-imports in `security/`), #1336 (ratchets become bans).


Source: https://github.com/dan-petty/devops-cli/issues/1309

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The code holds two test accommodations that no check catches. The first is an unused `run_subprocess` re-import in `security/ruff.py`. The second is a private `_prepare_cmd` alias in `core/process.py` that a test fake imports. No check stops a new `# noqa: F401` re-import from entering `src/`.

### Acceptance criteria
- Criterion 1: `src/devops_cli/security/ruff.py` imports no name it does not use.
  Verification: Run `rg -n 'noqa: F401' src/devops_cli/security/ruff.py` and confirm it prints nothing. Run `uv run ruff check --select F401 src/devops_cli/security/ruff.py` and confirm it passes.
- Criterion 2: No test patches a `devops_cli` name in the ruff scanner tests.
  Verification: Run `rg -n 'patch.*devops_cli' tests/` filtered to ruff scanner tests and confirm no result names `run_subprocess`.
- Criterion 3: The private alias `_prepare_cmd` is removed from all source and test files.
  Verification: Run `rg -n "_prepare_cmd" src tests` and confirm it prints nothing.
- Criterion 4: The test fake and `tests/test_process.py` use the public name `prepare_tool_cmd`.
  Verification: Run `rg -n 'prepare_tool_cmd' tests/support/fakes/process.py tests/test_process.py` and confirm both files reference the public name.
- Criterion 5: A `devops ci` row runs `ruff check --select F401 --ignore-noqa src` and fails when the finding count exceeds the ceiling.
  Verification: Add a `# noqa: F401` import to a file in `src/`, run `uv run devops ci`, and confirm the row fails. Remove the import and confirm the row passes. The ceiling is 14 (the sites #1332 owns).
- Criterion 6: The CI row runs on the stock runner with no install step and its job stays under 5 minutes.
  Verification: Inspect the workflow YAML for the row. Confirm it uses the stock runner and has no install step. Run the job and confirm it completes in under 5 minutes.
- Criterion 7: `uv run devops ci` passes in full.
  Verification: Run `uv run devops ci` and confirm exit code 0.

### Key questions
- **Does `security/ruff.py` use the `run_subprocess` name it imports?**: No. The module does not use the name, and no test at b170358e patches it. The import exists only as a `# noqa: F401` re-import. [sources: src/devops_cli/security/ruff.py]
- **Does `docs/TESTING.md` allow a test to import a private name from `devops_cli`?**: No. It states: 'no test imports a private name (one that starts with `_`) from `devops_cli`.' The fake at `tests/support/fakes/process.py:20` violates this rule. [sources: docs/TESTING.md, tests/support/fakes/process.py:20]
- **What is the ceiling for the new F401 re-import check?**: 14, the count of sites #1332 owns. The ceiling goes to zero when #1332 removes those sites. This issue removes the 15th site (`ruff.py:23`), leaving 14. (proposed)
- **Does this issue depend on #1309, #1332, or #1336 being delivered first?**: No. This issue adds the check kind that #1309 left out and removes one re-import. #1332 removes the other 14. #1336 turns ratchets into bans. None is a prerequisite. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "refactor/2166-the-unused-run-subprocess-re-import", "implement.job": "devops-cli-runner-20261101-055700-7856", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.pr": "2981", "implement.spend": "{\"requests\": 56, \"input_tokens\": 1460790, \"output_tokens\": 5883}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "66615c6ed035e49b7946cdc1ac39a238079f10aef45e9a5f8ef5c0ff45a51b8c", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "d0fb1427a8d66fcfc9aca2e9543611defe85ce5007aee6287dee5145bb677262", "stage.branch": "refactor/2166-the-unused-run-subprocess-re-import", "stage.file_cap": null, "stage.groups": "[[\"Remove unused re-import in security/ruff.py\", 3564], [\"Remove _prepare_cmd alias and update tests\", 3590], [\"Add F401 re-import ceiling CI row\", 3573]]", "stage.needs_split": null, "stage.pr": "2981", "stage.sha": "82703bfb9229728102134611c3fb3ebc39f38b83"} -->
