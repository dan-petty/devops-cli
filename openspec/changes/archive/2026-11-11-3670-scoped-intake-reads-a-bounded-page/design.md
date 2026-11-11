# Design

## Decisions

- **The triage lane and the scoped intake share one listing.** `service_jobs(state_dir)` gives the triage lane `intake_listing(state_dir)`, and the scoped update of a delivery opens its store with `intake_listing(service_manager.state_dir)`. Both resolve to `listing` in the state directory of the Service, `roadmap` under the data directory.
- **One writer for each file.** The scoped updates run on the triage lane's worker, one at a time with its rounds (`RepoWorker.enqueue_scoped`). Each repository has its own file. So no two writers race on one snapshot. The write is atomic, through a temporary file and a rename.
- **Only the triage lane.** The status and model lanes run in other threads at the same time. They keep the whole read, so the change adds no concurrent writer. A later change can give them the snapshot after the shared store of #4517.
- **The schema key.** `LISTING_SCHEMA_KEY` is the first 16 hex characters of the sha256 of `json.dumps(IssueRecord.model_json_schema(), sort_keys=True)`. A change of a field, a type or a description of the record changes the key, and each kept snapshot is read in full once. A change of the parse code that keeps the schema is not in the key: the full read every 24 hours corrects such a record, and a changed issue is parsed again at once. A test pins the key, so a change of the record shows in review.
- **The field name.** `ListingSnapshot.schema_key` replaces `version`. The project keeps no backward compatibility before 1.0.0. An old file fails validation, gives one warning and is read in full.

## Rejected alternatives

- **A cap of 10 pages on a scoped round** (the refine design of #3670): rejected. A capped listing holds only the newest issues. Intake compares each candidate with every item, so the duplicate check would miss old items.
- **The package version as the key, as before:** rejected. 117 releases in 7 days drop the snapshot about 17 times a day, and each drop costs a full read of 47 pages.
- **A hand-set integer as the key:** rejected. A person can forget to change it when the record changes; the hash changes by itself, and the pin test shows it.
- **The snapshot for every lane now:** rejected for this change. The status and model lanes would write the same file from other threads at the same time.
