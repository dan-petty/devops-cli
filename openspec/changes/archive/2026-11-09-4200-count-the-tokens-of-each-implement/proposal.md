# Proposal: Count the tokens of each implement Job once

## Why

The Service adds the tokens of a reported runner Job to `devops_cli_service_implement_tokens_total` (#4200). Since #4070 the record `implement.spend` holds the SUM of the spend of all Jobs of an item, not the spend of the last Job. `_emit_implement_metrics` still adds the whole sum at each report. So the tokens of an earlier Job count again at each later report, and the counter is too high for any item that needs more than one Job.

## What Changes

- Add the job record key `implement.spend_counted` (`ImplementRecordKey.SPEND_COUNTED`) in `src/devops_cli/roadmap/stores/store.py`. It holds, as decimal text, the token total that the Service has already added to the counter for the item.
- In `src/devops_cli/roadmap/implement/implement_submit.py`, `_report` reads `implement.spend` and `implement.spend_counted`, passes only the difference (the tokens of this Job) to `_emit_implement_metrics`, and writes the new total to `implement.spend_counted` in the same write that records `implement.job_state`. When the spend is below the counted total, the whole spend counts once and the counted total takes its value.
- In `src/devops_cli/roadmap/implement/implement_run.py`, the retry and the return to New clear `implement.spend_counted` in the same write that clears `implement.spend`.
- Add a row for `implement.spend_counted` to the record table of `docs/ROADMAP_WORKFLOW.md`, and a line for it to `tests/invariants/test_roadmap_implement_record_keys.py`.
- The change carries a spec delta for `roadmap-implement-job` (the token counter), so `skip_specs` is false. No setting, ConfigMap key or `Settings` field is added, removed or tightened.
- A record of an older version has `implement.spend` and no `implement.spend_counted`. It loads (`decode_job_record` reads a missing key as absent), and its first report counts the whole spend once.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: Token counter, A retry and a return to New clear the counted spend

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, `tests/roadmap/implement/test_roadmap_implement_records.py`, `tests/invariants/test_roadmap_implement_record_keys.py`

## Feasibility

- `src/devops_cli/roadmap/implement/implement_submit.py:304` reads `ImplementRecordKey.SPEND` and `:313` adds `input_tokens + output_tokens` of the whole record to `CONST_SERVICE_METRIC_IMPLEMENT_TOKENS`. `src/devops_cli/roadmap/implement/implement_run.py:515` loads the spend of earlier Jobs when the run is not a retry, and `:561` returns the earlier spend plus the spend of this Job. So the record is cumulative and the counter adds it whole.
- The test `test_two_jobs_of_one_item_count_each_token_once` reproduces it on `origin/main`: a first report with a record spend of 1,500 tokens and a second report with 4,000 tokens grow the counter by 5,500, not by 4,000. The run printed `assert ((1500.0, None), (5500.0, None)) == ((1500, '1500'), (4000, '4000'))`.
- A Prometheus counter cannot subtract: the registry wraps `prometheus_client.Counter` and has `increment_counter` only (`src/devops_cli/telemetry/metrics.py:88`), and the token series is an `InstrumentKind.COUNTER` (`tests/telemetry/test_telemetry_instruments.py:90`). So the Service must add a difference, and it must keep the counted total for each item. The job record is where `implement.spend` lives (`src/devops_cli/roadmap/stores/store.py:286`).
- `_JOB_RECORD_KEYS` (`src/devops_cli/roadmap/stores/store.py:613`) is built from the members of `ImplementRecordKey`, so a new member is a known key. `decode_job_record` keeps only known keys, so an older record without the key loads. The test `test_a_record_of_an_older_version_decodes_with_no_counted_spend_and_a_new_one_keeps_it` covers both.
- `implement.repair_rounds` is the sum of `self.outcomes` of one run (`src/devops_cli/roadmap/implement/implement_run.py:1052`), so it is per Job and does not double count. Only the tokens do.
- The `Settings` models are not touched, so no ConfigMap load test applies.

## Existing Tool Considered

The open, maintained `prometheus_client` 0.26.0 covers the counter but not the need: its `Counter` only increments, so it cannot remove tokens that the Service added before. No other open, maintained library keeps a counted total for each item. The change builds one record key, one small helper, two clears and the tests, about 40 lines. The written cost is about 8,000 tokens to build, about 2,000 tokens for each later fix, and about half a day of elapsed time. The change deletes no internal code.
