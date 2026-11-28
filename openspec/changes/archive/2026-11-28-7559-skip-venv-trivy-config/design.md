# Design

## Decisions

### Pass `--skip-dirs .venv` and `--skip-dirs **/.venv` in `TrivyConfigScanner.build_command`

Add `CONST_TRIVY_CONFIG_SKIP_DIRS: Final[tuple[str, ...]] = (".venv", "**/.venv")` in `src/devops_cli/config/constants.py` and extend `TrivyConfigScanner.build_command` (`src/devops_cli/security/trivy.py:231-246`) to append `("--skip-dirs", skip_dir)` for each entry. Local testing against Trivy v0.76 confirms `.venv` alone skips only a root `.venv/` directory whereas adding `**/.venv` also covers nested virtual environments (such as subpackage checkouts, #6636) while preserving `cmd[:3]` expected by existing contract tests (`tests/security/test_secops.py:96`).

### Remove obsolete `.venv/` entries from `.trivyignore.yaml`

With `TrivyConfigScanner` skipping `.venv`, the four `.venv/lib/python3.14/site-packages/harbor/...` entries in `.trivyignore.yaml` (which had already expired on 2026-11-26 through 2026-11-28) are obsolete and removed, together with their requirements in `openspec/specs/trivy-config-alerts/spec.md`.

## Rejected alternatives

- **Renew `.trivyignore.yaml` dates for three days**: Violates the root-cause rule (`AGENTS.md` rule 11); every three days `.venv` findings re-trigger `trivy-config-alerts.yml` (which already filed `#7275`, `#7276`, `#7392`, `#7393`, `#7558`, `#7559`).
- **Dismiss alerts `281` and `288`**: `SECURITY.md:132` forbids agents from dismissing alerts, and future scans would reopen new findings for any other installed package file in `.venv/`.
- **Edit `build_trivy_scan_cmd` for all scan types**: `tests/config/test_command_builders.py:39` verifies the exact `build_trivy_scan_cmd("src", "fs")` argument list without `--skip-dirs`; keeping IaC-only flags (`--ignorefile`, `--skip-dirs`) in `TrivyConfigScanner.build_command` leaves `fs` command construction unchanged.
