# Tasks

## 1. The store reads and their plan

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_store_contract.py` for `open_items` (open items only, `updated_at` set, and no read of every issue), `open_pulls` (draft, head branch, update time) and `repository_labels`, on both adapters; and in `tests/roadmap/test_roadmap_inbox_requests.py` for the plan entries of `StoreRequests` and `inbox_requests`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_inbox_requests.py`
- [x] 1.2 Add `Item.updated_at`, the models `OpenPull` and `RepositoryLabel`, and the three reads to `RoadmapStore`, `GitHubRoadmapStore` and `InMemoryRoadmapStore` (with `seed_pull` and `seed_label`); add `StoreRequests.open_items`, `open_pulls` and `repository_labels` and `inbox_requests`; add `declared_label_specs` to `title_labels.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_contract.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_inbox_requests.py tests/roadmap/test_roadmap_dry_runs.py`

## 2. The inbox

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_inbox.py` for the scenarios of "The inbox lists the gates of the jobs in order", "Each line has the number, the age and one clearing step", "Old claims are shown, never removed" and "Pull requests of people and agents are listed apart", with a fake repository
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py`
- [x] 2.2 Write `src/devops_cli/roadmap/inbox.py`: `read_inbox`, `inbox_requests` and `render_inbox`, with the constants `CONST_ROADMAP_INBOX_CLAIM_DAYS` and `CONST_ROADMAP_RELEASE_BRANCH_PREFIX` and the messages of the lines
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py`

## 3. The command

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_inbox_command.py` for the scenarios of "The inbox reads a bounded number of requests and writes none": the output, the reads counted, no write, no model, and the dry run with processes and sockets refused
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py`
- [x] 3.2 Add `devops roadmap inbox` with the class `request-plan`, its help and the read failure message
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py tests/invariants/test_dry_run_class_ratchet.py`

## 4. The documents and the archive

- [x] 4.1 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`
- [x] 4.2 Name `devops roadmap inbox` in `docs/ROADMAP_WORKFLOW.md` and remove the line of #2915 from "Planned changes"
  - Verification: `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`
- [ ] 4.3 Archive the change
  - Verification: `uv run devops openspec archive 2915-roadmap-inbox`

## Workflow follow-up

- Issue #2968 owns the inbox counts as gauges, the Grafana panel of the inbox and the image digest line. #2919 builds the age panel and does not wait for it.
- Until #2968 merges, the image digest that is not yet rolled stays out of the inbox. `devops argo cd apps status devops` reads it.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
