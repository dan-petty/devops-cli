# Tasks

## 1. Load the gold set and mark its stale entries

Kind: behavior. Reads: `src/devops_cli/ai/kb.py`, `tests/support/paths.py`, `src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md`. Changes: `src/devops_cli/ai/benchmark/gold_set.py` (new), `tests/fixtures/kb_gold_set/gold_set.json` (new), `tests/ai/benchmark/test_kb_gold_set.py` (new).
Adds: `GoldSetEntry`, `GoldSet`, `load_gold_set`, `mark_stale_entries`

- [x] 1.1 `tests/ai/benchmark/test_kb_gold_set.py::test_stale_entry_against_the_checked_in_folder_is_marked` covers the scenario Expected answer is gone against the checked-in article, and the same module covers Incomplete entry is rejected, Every entry is loaded, All three fact types are present, Expected source is absent and Mismatched version marks an entry stale
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_kb_gold_set.py` fails on the base
- [x] 1.2 Add `GoldSetEntry`, `GoldSet`, `load_gold_set` and `mark_stale_entries` to `src/devops_cli/ai/benchmark/gold_set.py`. `load_gold_set` reads the JSON under the fixture folder of `tests/support/paths.py`, rejects an entry with a missing field and names the entry and the field, and rejects a fact type other than tool, library or project. `mark_stale_entries` takes the gold set, a `repo_root`, a `kb_dir` and `tool_versions`; it marks an entry stale with a reason when its expected source is absent, when the expected answer is not in the source text, or when the source is an article under `kb_dir` whose relative path is in the drift list that `src/devops_cli/ai/kb.py:629:def load_matched_kb_manuals(` returns. Write 12 entries in `tests/fixtures/kb_gold_set/gold_set.json`, 4 for each fact type, each with a question, a repository path as its source, an expected answer, a fact type and a `reference` web page on example.com. One entry, `stale-bandit-version`, asks which Bandit version the manual pins and expects `Bandit is pinned to 1.7.5.` from `src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md`, which holds `tool:bandit@1.9.*` instead. `test_stale_entry_against_the_checked_in_folder_is_marked` loads that gold set from `FIXTURES`, calls `mark_stale_entries` with `repo_root=REPO_ROOT`, an empty temporary `kb_dir` and `tool_versions={}`, and asserts that the entry is stale with a reason that names the article path. The drift test writes a manual under `tmp_path/kb/it_domains/tools/` with the front matter `applies_to: ["tool:ruff@0.1.0"]`, `sources: ["https://example.com/ruff"]` and `reviewed: 2026-01-01`, and passes `tool_versions={"ruff": "0.2.0"}`
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_kb_gold_set.py` passes

## 2. Build the benchmark corpus and domain vocabulary from docs

Kind: behavior. Reads: `src/devops_cli/ai/benchmark/document_chunker.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`. Changes: `src/devops_cli/ai/benchmark/document_chunker.py`, `tests/ai/benchmark/test_embedding_benchmark.py`.
Adds: `document_corpus_paths`, `document_domain_index`, `_DOMAIN_DOCS_TOPIC_MAP`, `_read_domain_docs`

- [x] 2.1 `tests/ai/benchmark/test_embedding_benchmark.py::test_document_corpus_ignores_the_knowledge_base_folder` covers the scenarios Corpus survives folder removal and Eval task categories come from the docs, and the changed `tests/ai/benchmark/test_embedding_benchmark.py::test_infer_category_exact_word_boundaries_and_domain_classification` covers the docs vocabulary with a fixture root
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py` fails on the base
- [x] 2.2 Add `document_corpus_paths(repo_root)` and `document_domain_index(repo_root)` to `src/devops_cli/ai/benchmark/document_chunker.py`. `document_corpus_paths` returns the Markdown files of `docs/`, which holds the generated index `docs/KNOWLEDGE_BASE.md`, the top-level `AGENTS.md` and `README.md`, and the prompts under `src/devops_cli/ai/tasks/`, and adds no path of the bundled folder. `document_domain_index` builds the phrases and the top terms of each domain from the repository-relative pages of the new map `_DOMAIN_DOCS_TOPIC_MAP`, which `_read_domain_docs` reads under the given root with the size cap of the current reader. Delete `_DOMAIN_KB_TOPIC_MAP`, `_read_kb_topic_docs`, `_read_architecture_extra_docs` and `_get_domain_knowledge_base_index`, and pass the root to `_infer_category` at its two call sites and to `sample_evaluation_tasks`; `load_test_document_corpus` already takes `repo_root` at `repo_root: Path | None = None,` and passes `repo_root or Path.cwd()`, and `reset_document_chunker_cache` clears the new cache. The test writes a fixture root under `tmp_path` with the mapped docs pages of two domains, `AGENTS.md`, a docs index page and a knowledge base article that holds a marker word; it asserts that the corpus holds the index and no chunk holds the marker, that `document_domain_index` holds the terms of the fixture docs and no marker word, that a section with the fixture terms gets its domain, and that the corpus and the eval tasks of a run with the folder equal those of a run after its removal
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py` passes

## 3. Score a retrieval source on the gold set

Kind: behavior. Reads: `src/devops_cli/ai/benchmark/gold_set.py`, `src/devops_cli/ai/rag/retriever.py`, `tests/support/fakes/qdrant.py`, `tests/support/fakes/embeddings.py`. Changes: `src/devops_cli/ai/benchmark/gold_set_scorer.py` (new), `tests/ai/benchmark/test_gold_set_scorer.py` (new).
Adds: `GoldSetDocument`, `GoldSetScore`, `knowledge_base_source`, `project_digest_source`, `score_gold_set`, `format_score_block`

- [x] 3.1 `tests/ai/benchmark/test_gold_set_scorer.py::test_scorer_counts_one_hit_and_one_miss` covers the scenarios One hit of two entries is half and A missing expected source is no hit, and `tests/ai/benchmark/test_gold_set_scorer.py::test_score_block_holds_both_rows` covers Both sources produce a score row
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_gold_set_scorer.py` fails on the base
- [x] 3.2 Add `GoldSetDocument`, `GoldSetScore`, `knowledge_base_source`, `project_digest_source`, `score_gold_set` and `format_score_block` to `src/devops_cli/ai/benchmark/gold_set_scorer.py`. `knowledge_base_source` reads the articles of the bundled folder, and `project_digest_source` reads the chunks of the corpus of group 2. `score_gold_set` ensures a collection, upserts one point per document with the embedder's vector, the document path and the embedder's model in the payload, and searches each question through `src/devops_cli/ai/rag/retriever.py:457:def search(` with `top_k=5`, `score_threshold=0.0`, `rerank=False` and `hybrid=False`; a hit is a result whose chunk path is the expected source. The first test writes two documents under `tmp_path` and builds a two-entry gold set there: the first question is the exact text of the document that the source holds, so the fake embedder gives the same vector and that document ranks first; the second entry expects a document that neither the source nor the fixture folder holds, so it is a miss and is stale. The test asserts a hit rate at k=5 of 0.5, a stale share of 0.5 and the counts 1 of 2. The second test scores both adapters with the `qdrant` and `embedder` fixtures and asserts that the block holds a knowledge base row and a project digest row
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_gold_set_scorer.py` passes

## 4. Document the gold set, the docs corpus and the recorded score block

Kind: other. Reads: `docs/TESTING.md`, `src/devops_cli/ai/benchmark/gold_set_scorer.py`, `src/devops_cli/ai/benchmark/document_chunker.py`. Changes: `docs/TESTING.md`.

- [ ] 4.1 Add a section to `docs/TESTING.md` beside the fixture rules. It names `tests/fixtures/kb_gold_set/gold_set.json`, the loader, the scorer, the two source adapters and the k=5 depth, and it states that a stale entry names the source that no longer answers, that the gold-set test marks the stale entry against the checked-in article, that the scorer runs offline with the fake Qdrant client and the fake embedder, that the benchmark corpus and its domain vocabulary come from `docs/` under the repository root and never from the bundled folder, and that a person runs the scorer against the real Qdrant and embedding model in the devcontainer and pastes the Markdown score block into the pull request body
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/TESTING.md` with the gold set, the docs corpus and vocabulary, and the recorded score block
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: the gold set loads, each entry names a question and an expected source, and an entry whose expected answer is stale on the checked-in folder is marked.
- Group 3: A command or test helper scores a source with a recorded fake of Qdrant and the embedding model (no network in CI).
- Pending person: The score of the current folder and of the generated project digest is recorded in the pull request comment., The live score needs a running Qdrant and an embedding model, which CI holds none of. A person runs the scorer in the devcontainer and pastes the Markdown block into the pull request body, as the new section of `docs/TESTING.md` states.
- Group 2: The benchmark corpus is built from `docs/` and the index, so a later removal of the folder does not change it silently.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
