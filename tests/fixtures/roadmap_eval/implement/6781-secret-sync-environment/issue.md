## Problem
Design and owner decisions: dan-petty/devops-cli#6773 (design comment and decision comment of 2026-11-22). The command seals the release key into the environment `release`. `devops gh secret sync` (`src/devops_cli/github/secrets.py`) writes only repository secrets.

## Proposed remedy
- Add `--env <name>` to `devops gh secret sync`: the public key of the environment, the PyNaCl seal, and the PUT body on stdin. Read the value by keyring reference or from a file, and never print it.

## Acceptance criteria
- [ ] Tests with a fake GitHub show the environment routes and no secret value in output or logs.

## Person steps
None.

## Dependencies
None.


<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "claim.replaced_status": "New"} -->
