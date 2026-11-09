# Design

## Decisions

- **Record key.** The Service keeps the token total that it has already counted in the job record key `implement.spend_counted`, a decimal integer in text. It lives with `implement.spend`, which it tracks, and the table of record keys documents it.
- **One write.** `_report` computes the total and the delta from the two keys, puts the total in the marks of the `service_release` write that already records `implement.job_state`, and passes the delta to `_emit_implement_metrics`. No extra request is needed.
- **Clears.** Every place that clears `implement.spend` clears `implement.spend_counted` in the same write: the retry start in `implement_run.py` and the return to New. The new Job then starts its spend and its count at zero, and the counter keeps its earlier total.
- **Spend below the count.** When `implement.spend` is below `implement.spend_counted`, the record started again. The whole spend counts once and the counted total takes its value, so no later report goes negative.
- **Older record.** A record with `implement.spend` and no `implement.spend_counted` has counted nothing, so the first report counts the whole spend once. An item in flight at deploy can count its earlier Jobs one more time, once. The record cannot tell whether the old code counted them.

## Rejected alternatives

- **A gauge of the last spend.** The Service holds no series for each item, and a gauge needs one label value for each item number. Rejected.
- **A file in the data directory.** It adds a second store that a retry and a return to New must clear, and the record already holds `implement.spend`. Rejected.
- **A separate write before the counter.** Two writes can fail apart, and the record would then hold a total that the counter did not count. Rejected: one write holds the total with `implement.job_state`.
- **Read the counter back from the registry.** `prometheus_client.Counter` keeps one value for each label set (`repo`, `item_class`), not for each item, and it cannot subtract (`src/devops_cli/telemetry/metrics.py:88`). Rejected.
- **Add the negative difference when the spend fell.** A counter cannot decrease. Rejected.
- **Count nothing when the spend fell.** The tokens of the new Job are lost. Rejected.
- **Keep `implement.spend_counted` after a retry.** The new spend starts at zero, so a counted total above it hides the first tokens of the new spend. Rejected.
- **Start the counted total at zero without counting, for an older record.** The tokens of the first Job after deploy are lost. Rejected.
