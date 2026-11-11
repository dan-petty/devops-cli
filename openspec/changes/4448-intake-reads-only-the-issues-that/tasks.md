# Tasks

## 1. Intake reads the issues changed since its snapshot

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/output/file_writer.py`, `src/devops_cli/github/session_transport.py`. Changes: `src/devops_cli/roadmap/stores/listing_snapshot.py` (new), `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stores/test_listing_snapshot.py` (new), `tests/roadmap/stores/test_roadmap_store_install.py`.

- [x] 1.1 Write tests: the first run reads the whole listing and keeps a snapshot; a later run reads only the changed issues and keeps the other records; the watermark; the full read on `--full`, on another version and on an old full read; the warning on an unreadable snapshot and on a failed write; the sub-issue count; the refused repository name; the factory gets the listing
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/stores/test_roadmap_store_install.py` fails on the base
- [x] 1.2 Add `listing_snapshot.py` with `SnapshotStore`, `FileSnapshotStore` and `IncrementalListing`, read every issue through the listing in `GitHubRoadmapStore`, and pass the listing through `get_roadmap_store`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_listing_snapshot.py tests/roadmap/stores/test_roadmap_store_install.py tests/roadmap/stores/test_roadmap_github_store_paging.py`

## 2. The intake command and its dry run

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/intake/intake_requests.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/intake/intake_requests.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/intake/test_roadmap_intake_command.py`, `tests/roadmap/intake/test_roadmap_intake_dry_run.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 2.1 Write tests: a command run reads the whole listing, then `--full` reads it again, then a run reads the changes; the dry run lists the changed read and the full read with their conditions, and only the full read with `--full`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_command.py tests/roadmap/intake/test_roadmap_intake_dry_run.py` fails on the base
- [x] 2.2 Add `--full` to `devops roadmap intake`, open its store with the file snapshot under the data directory, and plan both reads in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_command.py tests/roadmap/intake/test_roadmap_intake_dry_run.py tests/ai/mcp/test_mcp_tool_listing.py`

## 3. Documents

Kind: documents.

- [x] 3.1 Describe the snapshot in `docs/roadmap/intake.md`, and regenerate the command documentation with `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The shared store of the Service implements `SnapshotStore` in #4517.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
