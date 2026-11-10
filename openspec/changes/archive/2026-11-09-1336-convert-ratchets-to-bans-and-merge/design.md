# Design

## Decisions

- **Bans replace ratchets with no ceilings**: Rather than comparing counts against ceilings, invariant tests assert zero directly (`== []` or `== 0`). Ceilings are deleted to prevent future raises.
- **Relocate test helpers to `tests/support/`**: Helper files (`cluster_secret_fakes.py`, `copilot_review_payloads.py`, `github_token_samples.py`, `keyring_isolation.py`, `llm_stream_fakes.py`, `project_board_fake.py`, `project_reconcile_fake.py`) are moved to `tests/support/` where shared test infrastructure belongs. The root `tests/` directory keeps only `conftest.py` and `__init__.py`.
- **Command inspection through public Typer/Click application**: `tests/invariants/test_dry_run_class_ratchet.py` accesses reachable commands via `typer.main.get_command(app)` instead of importing the private `_COMMAND_SPECS` dictionary.
- **`process_fake` replaces internal patch in manifest tests**: `tests/invariants/test_k8s_manifests.py` scripts kubectl calls with `process_fake` instead of patching `devops_cli.k8s.credentials.fetch_secret_data`.
- **Single source of truth for invariant subject files**: `docs/TESTING.md` lists the approved subject test files for `tests/invariants/`. The invariant layout test reads that list directly from `docs/TESTING.md` to prevent duplication and drift.
- **Ban validation via seed tests**: Each ban has a dedicated unit test creating a temporary file violation under `tmp_path` to prove that the invariant ban fires with the offending `path:line` and rule heading.

## Rejected alternatives

- **Keep ceiling constants set to zero**: Rejected because ceiling constants can be raised in subsequent pull requests, violating ADR 0005.
- **Exception list for internal patches**: Rejected by ADR 0005, which forbids exception lists.
- **Duplicate subject file lists**: Rejected keeping a hardcoded list in `test_source_tree.py` alongside `docs/TESTING.md`. The test parses the list from the documentation.
