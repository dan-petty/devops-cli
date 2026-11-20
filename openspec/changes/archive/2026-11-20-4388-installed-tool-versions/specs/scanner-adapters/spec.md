## REMOVED Requirements

### Requirement: Every scanner of the registry has a pinned program
**Reason**: The devtools image installs each scanner on PATH, and devops-cli is no package manager (owner decision of 2026-11-19). A test that compares the registry with `tools.lock` fails on the removal of the lock and holds no behavior of devops-cli.
**Migration**: A scanner with no program on PATH gives no result and no built-in pattern, as the registry scan test shows.
