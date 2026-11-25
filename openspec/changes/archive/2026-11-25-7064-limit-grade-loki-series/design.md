# Design

## Decisions

- **Place `| keep` at the end of the log pipeline before `[window]` (and before `| unwrap <count>` on efficiency queries).**: LogQL executes stages left to right, so placing `| keep` after field extraction and label filters ensures filter labels like `roadmap_job="implement"` and `result="drafted"` work while dropping high-cardinality pod/container/unused labels prior to range aggregation. Placing `| keep` before `| unwrap <count>` also satisfies LogQL's pipeline grammar for unwrapped metric queries, confirmed against live cluster Loki.
- **Anchor initial queries with `at=None` and split halves to a single captured `end` timestamp using `utc_text(...)`.**: Existing tests and helpers (`route_grade_replies`) key un-split instant queries without a `time` query parameter. Capturing `at = now or datetime.now(UTC)` once and passing `eval_at=utc_text(...)` only when recursively splitting a rejected count window keeps un-split URLs unchanged while guaranteeing gap-free, non-overlapping `[first_end - half, first_end]` and `[first_end, end]` partitions.
- **Halve only count queries (`COUNTS`, `CLASSES`, `FIRST_PASSES`, `DRAFTED`) down to a `1h` floor, matching HTTP 400 and `maximum number of series`.**: Count queries using `count_over_time` sum directly by `(labels)` key across disjoint sub-windows (`_sum_query_results`), whereas `quantile_over_time` efficiency queries cannot be merged from partial quantiles. Other HTTP 400 errors (such as syntax errors) are re-raised unchanged.

## Rejected alternatives

- **Increase Loki's `max_query_series` server limit above 500.**: Raising the cluster-wide series cap increases Loki memory usage across all queries and masks cardinality growth from stream and extracted labels.
- **Pre-split all `[7d]` windows into fixed `[48h]` or `[24h]` chunks unconditionally.**: Unconditional splitting adds unnecessary Loki round trips when `| keep` or `--repo` already keeps series below 500, and cannot merge quantile queries.
- **Remove `version` from `COUNTS` aggregation.**: The grade report requires per-version rows for versions with 10 or more attempts (`_MIN_VERSION_ATTEMPTS`).
