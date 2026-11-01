## Problem Description

`devops ai cost report` stops with a `ValueError` when the spend ledger holds a served_by value that `urllib.parse.urlsplit` cannot read.

- `_is_single_server_local` in `src/devops_cli/ai/spend/pricing.py` calls `urlsplit(clean)` on the stored served_by value, with no guard.
- For `http://[::1`, `urlsplit` raises `ValueError: Invalid IPv6 URL`, and the report command fails before it shows a table.
- `extract_served_by` now refuses such a header value, so a new row cannot hold one. Ledger rows from before that change can hold one.

## Reproduction Steps

1. Record a gateway call in a spend ledger with `served_by="http://[::1"` (`SpendLedger.record_request`).
2. Run `devops ai cost report --by backend` against that ledger.

## Expected vs Actual Behavior

- Expected: the report shows the row, and the serving backend shows as `unknown`.
- Actual: the command exits 1. The traceback ends in `pricing.py`, `_is_single_server_local`, `urlsplit(clean)`, with `ValueError: Invalid IPv6 URL`.

## Environment Diagnostics

Found with an offline probe at `4226904e`, while the change for #1110 was tested. The probe used a temporary ledger and `typer.testing.CliRunner`.

## Logs, Traces, or Terminal Output

```
File "src/devops_cli/ai/spend/pricing.py", in _is_single_server_local
    if clean in CONST_LOCAL_TRANSPORT_LABELS or urlsplit(clean).scheme == "http+unix":
ValueError: Invalid IPv6 URL
```

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
The `devops ai cost report` command crashes with an unhandled ValueError when a spend ledger row holds a served_by value that urllib.parse.urlsplit cannot parse, such as http://[::1. The function _is_single_server_local calls urlsplit without a guard. New rows cannot hold such a value because extract_served_by now refuses it, but legacy rows from before that change can. The report must show the row and treat the backend as unknown instead of exiting with a traceback.

### Acceptance criteria

### Requirement: Report does not crash on unparseable served_by
The report command SHALL NOT raise an unhandled ValueError when a ledger row holds a served_by value that urlsplit cannot parse.

#### Scenario: Ledger row with served_by http://[::1
- **WHEN** A spend ledger row has served_by set to http://[::1 and the user runs devops ai cost report --by backend
- **THEN** The command exits 0 and prints the report table without a traceback

### Requirement: Unparseable backend shows as unknown
The report SHALL display the serving backend as unknown for a row whose served_by value urlsplit cannot parse.

#### Scenario: Backend column for unparseable value
- **WHEN** The report renders a row whose served_by is http://[::1
- **THEN** The backend column for that row shows unknown

### Requirement: Valid served_by values still resolve
The report SHALL resolve a valid served_by value to its local or hosted classification as before.

#### Scenario: Valid local backend still detected
- **WHEN** A ledger row has served_by set to ``http://localhost:11434`` and the user runs devops ai cost report --by backend
- **THEN** The row is classified as local and the backend column shows the resolved value

### Existing Tool Considered
No external tool covers this need. The fix is a try-except ValueError guard around one urlsplit call in src/devops_cli/ai/spend/pricing.py, plus one test. The written cost is roughly 10 lines of code and 15 lines of test, kept in the same file. No new dependency is added.

### Key questions
- **What should _is_single_server_local return when urlsplit raises ValueError on the input string?**: Return False, treating the server as not local. This lets the pricing path proceed and the report show the row with the backend as unknown. (best practice) [sources: src/devops_cli/ai/spend/pricing.py:243, openspec/changes/archive/2026-10-28-1110-reply-server-origin/design.md:33]
  - Chosen: Return False on ValueError. The value is not a valid URL, so it cannot be a local server. Returning False lets the caller proceed with normal pricing. This matches the expected behavior in the issue body.
  - Rejected: Raise a custom domain error. The project prohibits raising bare built-in exceptions in domain logic (docs/SDLC.md:124), but a custom error would still crash the report. The issue expects the row to show, not to error.
  - Rejected: Pre-validate the string with a regex before urlsplit. A regex check adds a second code path to maintain and does not cover every malformed input that urlsplit rejects. A try-except is simpler and covers all cases.
- **Does the project already guard urlsplit calls elsewhere?**: Yes. _is_local_host in the same file catches ValueError from ipaddress.ip_address, and the pattern of catching ValueError around a parse call is established in this module. [sources: src/devops_cli/ai/spend/pricing.py:230]
- **Is this fix independent of issue #1110?**: Yes. #1110 changes extract_served_by to refuse bad values at write time. This issue adds a guard at read time for legacy rows. The guard works whether or not #1110 is merged. [sources: openspec/changes/archive/2026-10-28-1110-reply-server-origin/design.md:33, src/devops_cli/ai/client/network.py:99]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "fix/2462-devops-ai-cost-report-shows-a", "implement.job": "devops-cli-runner-20261101-073656-4a2c", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.pr": "2990", "implement.spend": "{\"requests\": 17, \"input_tokens\": 335674, \"output_tokens\": 1820}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "cfa774ef3df206bd9af3c92c4f6678b45b6e29ccd32f004451ba9a1021b966ba", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "96d9f8e8a1040fdba975f306a6d3c9cbebdeda14d9cab5ed1c0c3c5f51d84d99", "stage.branch": "fix/2462-devops-ai-cost-report-shows-a", "stage.file_cap": null, "stage.groups": "[[\"Guard urlsplit in _is_single_server_local and add tests\", 2803]]", "stage.needs_split": null, "stage.pr": "2990", "stage.sha": "cc24160343051403c62c609cb02a78812e0de398"} -->
