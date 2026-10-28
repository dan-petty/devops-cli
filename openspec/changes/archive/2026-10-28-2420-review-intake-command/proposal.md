# Proposal

## Why

Issue #2420, part 3 of #883: nothing turns a review finding about merged code into a roadmap item. `docs/SELF_IMPROVEMENT.md` asks a person or an agent to file each finding by hand. On 2026-10-28 the owner chose, on #883, an explicit command for the hand-off, and not a side effect of each `review path` run, because each finding costs one model call in intake. Part 1 (#2415) records the checkout of a session and decides whether the session is on merged code. Part 2 (#2419) gives the marker that an issue filed from a finding carries, and the lookup that leaves out a finding that an issue already carries.

## What Changes

- New command `devops review intake [SESSION]`. It reads findings.json of the session (the latest when no session is given) and hands each qualifying finding that no issue settles to roadmap intake, one candidate for each finding, through `intake_candidate`. It has the modes of `devops roadmap intake`: `--dry-run` makes no request, `--plan` (the default) reads GitHub and calls the model and writes nothing, and `--confirm` files and places each candidate.
- A finding qualifies when its fingerprint is a fingerprint v2 and its verdict is not INVALIDATED or MITIGATED. Admission writes the fingerprint v2 of each admitted tool finding into findings.json and keeps a suppressed finding out of it, so each such finding is an OPEN tool finding. No code sets CONFIRMED yet, and findings.json stores no state, so the CONFIRMED findings join with #2414.
- Each candidate has the title `fix: <finding title> (<location>)`. Its body cites the session, the location, the tool, the severity, the verdict, the description, the cited code, the fix and the verification criteria, and it ends with the marker of the finding's fingerprint.
- The command refuses a session that is not on merged code, before any request, and says why: not a path review, no recorded checkout, a working tree with a change, or a commit that `origin/main` does not hold. The repository that decides is the checkout of the working directory.
- The command refuses, before any request, a candidate whose text looks like it holds a secret, and names its finding.
- `is_on_merged_code` gives its reason through a new `why_not_on_merged_code`.
- When `review path` keeps a session of a clean tree that has qualifying findings, it prints their count and the command. It runs no git, sends no request and calls no model for that line.
- `docs/SELF_IMPROVEMENT.md` routes the findings about merged code through the command.
- A new error, `ReviewHandOffRefusedError` (`REVIEW_HAND_OFF_REFUSED`), names the refusal.
- The command and the `review path` line change what a consumer sees, so the change carries spec deltas: ADDED requirements in `review-merged-code` and `review-filed-findings`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `review-merged-code`: a session that is not on merged code says why, and `review path` names the hand-off.
- `review-filed-findings`: which findings qualify, the candidate of a finding, and the `devops review intake` command.

## Impact

- New `src/devops_cli/review/handoff.py`.
- `src/devops_cli/review/checkout.py`, `src/devops_cli/review/fingerprint.py`, `src/devops_cli/review/filed_findings.py`.
- `src/devops_cli/commands/review.py`, `src/devops_cli/ai/review/runner.py`.
- `src/devops_cli/exceptions/ai.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- `tests/support/fakes/model.py`: the model fake also embeds through the `Embedder` protocol, so a test passes it to `GatewayIntakeModel`.
- New tests in `tests/review/test_review_intake_handoff.py`.
- `docs/SELF_IMPROVEMENT.md`, and the files that `devops docs generate --sync-readme` rewrites.

## Feasibility

Checked on `origin/main` 4226904e, 2026-10-28.

- `review/checkout.py` has `is_on_merged_code(session, repository)` (#2415). `review/filed_findings.py` has `finding_marker`, `read_filed_findings` and `FiledFindings.unfiled` (#2419). `roadmap/intake.py` has `intake_candidate(store, candidate, repo=, model=, confirm=)`, which `survey/intake.py` already calls for one candidate at a time.
- `pipeline._sanitize_admitted_candidate` sets `SavedFinding.fingerprint` to the admitted finding's `fingerprint_v2`, a SHA-256 in lowercase hex (`review/fingerprint.py`). `_admit_single_candidate` returns no saved finding for a SUPPRESSED one. So a saved finding with a fingerprint v2 is an admitted, OPEN tool finding, and its `status` holds only the verdict.
- `FindingState.CONFIRMED` is defined in `review/state.py`, but no code sets it, and `SavedFinding` has no state field. #2414 (open) adds that.
- `devops roadmap intake --title <t> --body-file <f> --dry-run` (2026-10-28) lists the requests for one new candidate: one listing of every issue, which the store keeps for the run; one read of `.github/labels.yml`; one embedding call; one model call for the proposal; and evidence reads only when the model cites evidence. With `--confirm`, a placed candidate adds about 11 REST requests.
- `GatewayIntakeModel.embed` uses `EmbeddingsEngine`, which caches each embedded text, so the comparison set that each candidate embeds again reaches the gateway only for texts that the cache does not hold.

## Existing Tool Considered

`devops roadmap intake` is the one entry point for new items (#742), and the command calls it and builds no second filing path. Git decides the merged-code test, GitHub issue search finds the filed findings (#2419), and the model and the duplicate check are intake's own. The change adds one module that turns a saved finding into an intake candidate, and one command. It deletes the step in `docs/SELF_IMPROVEMENT.md` that files a finding by hand.
