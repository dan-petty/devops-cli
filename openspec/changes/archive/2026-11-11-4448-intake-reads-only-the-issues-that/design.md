# Design

## Decisions

- **Snapshot and `since`.** The CLI keeps one JSON file for each repository under the data directory, `roadmap/listing/<owner>/<name>.json`. A run reads the issues changed since the watermark and merges them into the snapshot. A file for each repository keeps a write for one repository away from the record of another.
- **Order of the changed read.** `sort=updated&direction=desc`. The listing is paged by offset, and an issue that changes during the read moves to the first page, which the read has. No issue that did not change moves out of a page that the read has not reached.
- **Watermark.** The earlier of the start of the read and the newest `updated_at` that GitHub gave, less 60 seconds. The start of the read covers a change during the read. GitHub's own time covers a local clock that is ahead of GitHub's, as a WSL2 clock can be after a sleep. The overlap costs at most a few issues on the first page.
- **Version and age.** The snapshot holds the version of devops-cli that parsed the records. Another version reads the whole listing, because the parse of a body or the known keys of a job record can change between versions. A snapshot whose last full read is 24 hours old or older is read in full, so an issue that was deleted or transferred, or a change that moved no `updated_at`, stays at most one day.
- **Sub-issue count.** GitHub does not move the `updated_at` of a parent when a sub-issue joins or leaves it (#4517 timeline, 2026-11-11). When a changed issue joined or left a parent that the read did not return, the merge moves the count of that parent by one. Intake leaves an issue with sub-issues out of the comparison set (#1985), so a stale count of zero would let a tracker in.
- **Failures.** A snapshot that cannot be read gives a warning and a full read. A failed write gives a warning, and the rename keeps the earlier file whole; the listing that the run read is complete, so the run goes on.
- **Seam.** `SnapshotStore` (`load`, `save`) is the place that keeps the snapshots. `FileSnapshotStore` is the CLI's. A shared store for the Service (#4517) implements the same two methods. `IncrementalListing` holds the policy, and `GitHubRoadmapStore` takes it as `listing`; `get_roadmap_store` passes it to an installed factory too.
- **Scope.** Only `devops roadmap intake` passes a listing. The Service poll and `devops roadmap run` keep the full read (ADR 0017: the poll reconciles).

## Rejected alternatives

- **gidgethub `cache=` on disk, or hishel.** The default listing order is by creation, newest first, so each new issue moves every page and changes each ETag; on 2026-11-11, 47 issues changed in one hour. The 45 pages pass through the rate limiter, which paces a 304 too, and neither cache keeps a parsed record, so the parse of every body stays.
- **`direction=asc`, as the refine section proposed.** An issue that changes during a read of more than one page moves to the end, the later pages move back by one, and one issue that did not change is skipped. Its `updated_at` is before the next watermark, so no later run reads it until the next full read.
- **The end time of the read, or only the newest `updated_at`, as the watermark.** The end time misses an issue that changed during the read. The newest `updated_at` alone misses an issue that changed during a full read on a page that the read had read.
- **A snapshot in the session cache only.** It does not survive the process, which is the cause of the item.
- **Start empty when no snapshot is kept.** Each issue would look new, and intake would compare a candidate with nothing.
