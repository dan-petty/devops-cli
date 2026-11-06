# Proposal

## Why

Items that share one root cause are filed one at a time, and nobody groups them. #1127 asks for a consolidation job that proposes groups. The full design has about 25 requirements: a command, two model passes, a plan file, four apply shapes, new store writes, an MCP mirror and a weekly row. The earlier refine round proposed four parts, and the estimate is 180,000 tokens and 4 weeks. That does not fit one pull request (#1127).

This change is part 1: the shared shortlist. It is the base that the other parts need, and it needs no model call. Parts 2 to 4 are filed as #3740 (plan), #3743 (apply) and #3745 (MCP mirror and weekly row). The live-board check was already moved to #3635.

## What Changes

- One function, `nearest`, in `roadmap/nearest.py`. It ranks vectors by cosine similarity and returns the closest. The intake planner calls it, so intake and the new job share one matcher. Intake behavior does not change, and the intake tests do not change.
- A new module `roadmap/consolidate_shortlist.py`. For each open item it builds a shortlist of the other open items from three tool signals, before any model call:
  - citations: the paths and the backticked identifiers that two bodies both cite, read with `cited_paths` and `cited_identifiers` of refine, from the text of a person only. A path or an identifier that more than `DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION` open items cite is too common to show a shared cause, so it is ignored;
  - links: blocked-by, sub-issue and parent, the lines "Depends on", "Related", "Split from", "Split off" and "Merged into", and the section "Dependencies" of refine;
  - embedding: the `DEFAULT_ROADMAP_INTAKE_SHORTLIST` nearest items.
- Each member of a shortlist carries its evidence. `assign_groups` puts each item in one group at most, as the anchor or as a member. The stronger evidence wins (a shared path and identifier, then a shared path, then a shared identifier, then a link, then an embedding rank), and a tie goes to the lower anchor number. A member does not anchor a group. The code makes no transitive join and builds no graph.
- An embedding cache by body hash in the data directory (`roadmap/consolidate/embeddings.json`). A run over an unchanged board embeds nothing. The hash covers the text of a person, not the sections that refine and the alternatives job write.
- A new store read, `RoadmapStore.blocked_by(number)`, on the GitHub store (`GET /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by`) and on the in-memory store. `IssueRecord.blocked_by` holds the count from the issue listing (`issue_dependencies_summary.total_blocked_by`), so a run reads only the issues that have blockers.
- A consumer observes the new reads, so the change carries a spec delta. No command, option or message changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-consolidate-shortlist`: The shortlists of the consolidation job, their evidence, the contest rule and the embedding cache.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/nearest.py` (new), `src/devops_cli/roadmap/consolidate_shortlist.py` (new), `src/devops_cli/roadmap/intake.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/roadmap/test_roadmap_nearest.py` (new), `tests/roadmap/test_roadmap_consolidate_shortlist.py` (new), `tests/roadmap/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap_github_fake.py`
- Documents: none. `git grep -n -i "shortlist\|consolidat" -- '*.md'` finds no document that names the job.

## Feasibility

Checked against `origin/main` at `29309f04` on 2026-11-06.

- The earlier comment on #1127 (2026-11-05) lists five stale premises. This change checked each one in the code.
  - The store has no read of blocked-by links. `git grep -n "blocked_by" src/devops_cli/roadmap/store.py` prints nothing. The REST endpoint exists: `uv run devops gh api repos/dan-petty/devops-cli/issues/3635/dependencies/blocked_by` answered `[]` with status 200. The issue payload carries `issue_dependencies_summary` with `blocked_by`, `blocking`, `total_blocked_by` and `total_blocking`; `uv run devops gh api repos/dan-petty/devops-cli/issues/1127` showed all four. So this change builds the read.
  - `write_issue_body` (`store.py`) and `add_sub_issue` (`store.py`) exist. This part needs neither. Parts 2 and 3 use them.
  - `GitHubRoadmapStore.close` sends one REST `PATCH` with `state_reason`, and `CloseReason` holds `DUPLICATE`. No `duplicateIssueId` call exists. Part 3 (#3743) confirms the REST value before it uses it. This part closes nothing.
  - Roadmap fields are labels (ADR 0016). Parts 2 and 3 read the status labels, not a board Status. This part reads no status.
  - The matcher of intake is `_Planner._shortlist` in `intake.py`, and the cosine function is `devops_cli.ai.vector_similarity.cosine_similarity`. The citation readers are `cited_paths` and `cited_identifiers` in `refine.py`. The body hash is `hash_text` in `body_hash.py`.
- No other pull request changes these files: `git log origin/main --oneline -- src/devops_cli/roadmap/intake.py` shows no open work on the matcher, and the agents that run now hold other issues.

## Existing Tool Considered

- GitHub duplicate detectors: the alternatives check of 2026-10-30 found none that groups all open items. They compare one new issue with the board.
- networkx: the design needs no graph. A shortlist for each anchor and a fixed tie-break give the groups, so the change adds no dependency.
- numpy or scikit-learn for the nearest items: the board has fewer than 400 open items. `cosine_similarity` in `vector_similarity.py` already ranks them, and intake uses it. The change reuses it.
- The embedding client of intake (`GatewayIntakeModel.embed`) embeds the texts. The cache is one JSON file, written with the standard library. `diskcache` would add a dependency for one small file.

The cost to build is about 60,000 tokens. To keep and fix it costs about 8,000 tokens a year. The elapsed time is about 1 day. The change deletes the inline ranking in `_Planner._shortlist`.
