# Design

## Decisions

### Renew DS-0029 for 3 days per SECURITY.md
SECURITY.md states that an agent judges an alert below CRITICAL with an ignore entry of 3 days, up to 14 days total.
The Dockerfile is part of the installed Harbor package under `.venv`.
Renew the entry through 2026-11-26.

### Reference tracking issue in statement
The statement references tracking issue #6856 alongside #5947.

## Rejected alternatives

- **Edit the Dockerfile in .venv**: A virtual environment package install overwrites local changes.
- **Set 90 days**: Only the repository owner can approve an ignore longer than 14 days. An agent follows the 3-day renewal limit.
- **Dismiss the alert**: An agent does not dismiss alerts in code scanning; a person must do so if appropriate.
