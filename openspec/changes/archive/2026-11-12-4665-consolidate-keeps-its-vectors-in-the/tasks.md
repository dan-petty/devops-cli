# Tasks

## 1. The job keeps its vectors in the shared tiers

Kind: behavior. Reads: `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/rag/embedding_disk_cache.py`, `src/devops_cli/roadmap/intake/intake_model.py`. Changes: `src/devops_cli/roadmap/consolidate_shortlist.py`, `src/devops_cli/roadmap/consolidate_judge.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/constants.py`, `tests/commands/test_roadmap_consolidate_cmd.py`, `tests/roadmap/test_roadmap_consolidate_shortlist.py`, `tests/roadmap/test_roadmap_consolidate.py`, `tests/roadmap/test_roadmap_consolidate_judge.py`.

- [x] 1.1 Write failing tests: a second run through the command sends no embedding request and counts disk hits, the folder of the job holds the plan only, a section of a job is no part of the embedded text, and items with the same text are embedded once; keep tests that an edit sends one text and another model sends every text again
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_consolidate_cmd.py tests/roadmap/test_roadmap_consolidate_shortlist.py` fails on the base
- [x] 1.2 Give `GatewayEmbedder` the disk tier `embedding_disk_cache()`, send each text once from `embed_issues`, and remove the `embeddings.json` code, its constant, `Edges.embedding_model` and `GatewayEmbedder.model`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_consolidate_cmd.py tests/roadmap/test_roadmap_consolidate_shortlist.py tests/roadmap/test_roadmap_consolidate.py tests/roadmap/test_roadmap_consolidate_judge.py`

## 2. No code names the file

Kind: other.

- [x] 2.1 Confirm that no code reads or writes the removed file
  - Verification: `$ ! git grep -n -F embeddings.json src tests`
