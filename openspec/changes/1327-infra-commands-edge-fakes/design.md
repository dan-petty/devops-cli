# Design

## Overview

The 17 infra command test modules test CLI command adapters under `src/devops_cli/commands/`. They verify command-line option parsing, argument validation, process dispatch, formatting, and exit codes. This design refactors these tests to exercise commands over edge fakes and seams rather than monkeypatching internal Python functions.

## Architectural Changes

1. **Domain Extraction**:
   - Move Terraform resolution helpers from `commands/tf.py` into public functions in `tf/`.
   - Move secret-leak detection helpers from `commands/config.py` into public functions in `config/`.
   - Move Cloudflare bypass-IP resolution helpers from `commands/cloudflare.py` into public functions in `cloudflare/`.
   - Move Vault path validation helpers from `commands/vault.py` into public functions in `security/` or `vault/`.
   - Maintain backwards-compatible aliases in command modules where unmigrated tests or callers require them until subsequent issues complete.

2. **Seam & Edge Routing in Tests**:
   - Subprocesses: route external tool commands (`terraform`, `tofu`, `docker`, `kustomize`, `kubectl`, `argocd`, `vault`, scanners) through `process_fake`.
   - Keyring: route credentials through `keyring_store`.
   - HTTP: route endpoints through `respx` fakes.
   - Valkey: route Valkey commands through `valkey_fake`.
   - CLI execution: use the `cli` test fixture instead of instantiating `CliRunner()`.

3. **Ratchet Ceilings**:
   - Clean up internal patch targets and private imports, maintaining compliance with invariant ratchet tests.

## Rejected Alternatives

- **Keep internal function monkeypatching (`patch("devops_cli.commands...")`)**:
  - Rejected: Internal monkeypatching couples tests to private implementation details and breaks when refactoring internal function signatures.
- **Spin up live local daemons (real Valkey, local Docker daemon, real HashiCorp Vault server)**:
  - Rejected: Requires external daemons, increases test execution time, and violates the hermetic offline test requirement in `docs/TESTING.md`.
- **Pass explicit double instances through Typer CLI command signatures**:
  - Rejected: Bloats user-facing command-line options and signatures with test-only parameters.
