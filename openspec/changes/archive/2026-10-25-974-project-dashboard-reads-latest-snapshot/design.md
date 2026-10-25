# Design

## `last_over_time` over the dashboard's range

Each gauge panel reads `last_over_time(<metric>[$__range])`: the latest sample of each series in the time range of the dashboard. A snapshot sent every 15 minutes, or one sent hours ago by hand, still shows; a range with no sample shows no data.

Known limit: a series that a later snapshot no longer sends, such as a referrer that leaves the top ten, keeps its last value until it leaves the range. The panel descriptions say that a panel shows the latest value of each series. A query that keeps only the series of the newest snapshot needs the time of each sample (`timestamp()` compared with the newest), which this change does not add.

Rejected: a fixed window equal to the interval, such as `[20m]`. It shows nothing while the roadmap Service is stopped, which is now, and it breaks when the interval changes.

Rejected: keep `or vector(0)`. A 0 says that the repository has no releases, stars or clones; no data says that no snapshot was sent, which is the truth.

## The names

The 13 project gauges drop `_total`. Prometheus keeps the suffix for counters, and the collector's suffix translation is off (`k8s/otel/values.yaml`), so the name devops-cli gives is the name each consumer sees. The old series stop at the next snapshot, and the new names start with it.

Rejected: keep the names and only fix the queries. A gauge named like a counter misleads each query written later, and the new invariant would need an exception list.

## The invariant

The old invariant asked for `rate(` or `increase(` and skipped the project dashboard, because its series are snapshots. The new invariant reads the kind of each series from `INSTRUMENTS`, so the same rule covers every devops-cli dashboard with no exception.
