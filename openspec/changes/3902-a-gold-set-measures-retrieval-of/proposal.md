# Proposal

## Why

The bundled knowledge base of 75 manuals grounds the review loop and the AI commands, and no labelled set measures whether retrieval answers the questions those jobs ask (#3902). The audit of 2026-11-07 found 15 of 26 checked claims stale, so the old source is no clean reference, and nobody can say whether a replacement source answers the same questions as well. The change adds a gold set, a stale marker that runs against the checked-in sources, and an offline scorer, and it moves the benchmark corpus and its domain vocabulary to docs and the generated index, so a later removal of the folder changes neither.

## What Changes

- Add `src/devops_cli/ai/benchmark/gold_set.py`, which loads the checked-in gold set, rejects an entry that lacks a question, an expected source, an expected answer or a fact type, and marks an entry stale with a reason.
- Add `tests/fixtures/kb_gold_set/gold_set.json` with 12 entries, 4 for each of the tool, library and project fact types, each naming a repository path and a primary web page, and one of them the stale Bandit version claim that the checked-in article no longer answers.
- Add `src/devops_cli/ai/benchmark/gold_set_scorer.py`, which ranks the documents of one source through the `search` method of the retriever, reports hit rate at k=5 and the stale share, and prints a Markdown block with a row for the knowledge base folder and a row for the project digest.
- Build the benchmark document corpus from `docs/`, which holds the generated knowledge base index, `AGENTS.md`, `README.md` and the task prompts, and delete the three reads of the bundled folder from `src/devops_cli/ai/benchmark/document_chunker.py`.
- Build the benchmark domain vocabulary, and so the eval task categories, from the docs pages of a checked-in map under the repository root that the caller passes, and delete `_get_domain_knowledge_base_index`, `_DOMAIN_KB_TOPIC_MAP`, `_read_kb_topic_docs` and `_read_architecture_extra_docs`.
- Add `tests/ai/benchmark/test_kb_gold_set.py` and `tests/ai/benchmark/test_gold_set_scorer.py`, and change `tests/ai/benchmark/test_embedding_benchmark.py` to assert exact scores from the fakes, the docs corpus and the docs vocabulary, with no network. The gold-set test loads the checked-in set and asserts that its stale entry is marked against the checked-in article.
- Document the gold set, the two source adapters, the docs corpus and its vocabulary, and the recorded score block in `docs/TESTING.md`.
- Add the capability `ai-retrieval-gold-set` to the spec delta, with the gold set, the stale marking, the offline scorer, the corpus and the domain vocabulary requirements.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-retrieval-gold-set`: Gold set loads and validates, Gold set covers three fact types, Stale entries are marked, Version drift marks an entry stale, Scorer reports hit rate and stale share, Scorer runs offline, Score block for both sources, Benchmark corpus from docs and index, Benchmark domain vocabulary from docs

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/benchmark/gold_set.py`, `src/devops_cli/ai/benchmark/document_chunker.py`, `src/devops_cli/ai/benchmark/gold_set_scorer.py`
- Documents: `docs/TESTING.md`
- Tests: `tests/fixtures/kb_gold_set/gold_set.json`, `tests/ai/benchmark/test_kb_gold_set.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/benchmark/test_gold_set_scorer.py`

## Feasibility

- The probes read: The path `tests/fixtures/kb_gold_set/gold_set.json` is no file of the staging commit. No commit in the history deleted or renamed it. The gold set is therefore a file to create and no false premise.
- The probes read: The path `docs/KNOWLEDGE_BASE.md` is a file of the staging commit. `read_file` on it showed `docs/KNOWLEDGE_BASE.md:3:The bundled Knowledge Base provides **75 operational and architectural manuals**`, which confirms the 75 manuals that the issue names.
- `read_file` on `src/devops_cli/docs/generator.py` lines 1360-1370 showed `src/devops_cli/docs/generator.py:1365:results["KNOWLEDGE_BASE.md"] = self.generate_knowledge_base_index()`, so the index that the corpus keeps is generated and checked in.
- The probes read: The path `uv.lock` is a file of the staging commit. The probes read: The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`, `tests/fixtures/research/repo/src/devops_cli/tools_lock/tools.lock`. `read_file` on `src/devops_cli/ai/kb.py` lines 546-584 showed `src/devops_cli/ai/kb.py:def _resolve_matching_context` reads no lock file itself, so passing `kb_dir` and `tool_versions` to `src/devops_cli/ai/kb.py:629:def load_matched_kb_manuals(` keeps the test off the checkout's lock files.
- `read_file` on `src/devops_cli/ai/benchmark/document_chunker.py` lines 386-400 showed `src/devops_cli/ai/benchmark/document_chunker.py:395:domain_index = _get_domain_knowledge_base_index()`, whose body at `src/devops_cli/ai/benchmark/document_chunker.py:205:kb_dir = get_knowledge_base_dir()` reads the bundled folder, so the corpus and the task categories would change when the folder is removed.
- `read_file` on `src/devops_cli/ai/benchmark/document_chunker.py` lines 460-520 showed the other reads that group 2 deletes: `src/devops_cli/ai/benchmark/document_chunker.py:472:candidate_paths.extend(list_knowledge_base_articles())`, `src/devops_cli/ai/benchmark/document_chunker.py:491:kb_dir = repo_root / "src" / "devops_cli" / "ai" / "knowledge_base"` and the folder-only fallback `src/devops_cli/ai/benchmark/document_chunker.py:509:for p in list_knowledge_base_articles():`.
- `read_file` on the same file lines 50-70 and 320-360 showed `src/devops_cli/ai/benchmark/document_chunker.py:58:_DOMAIN_KB_TOPIC_MAP: dict[str, list[str]] = {`, `src/devops_cli/ai/benchmark/document_chunker.py:328:cat = self._infer_category(c.heading, c.text)` and `src/devops_cli/ai/benchmark/document_chunker.py:355:category = self._infer_category(chunk.heading, chunk.text)`, so the vocabulary and its two call sites take the repository root from the caller.
- `read_file` on `tests/ai/benchmark/test_embedding_benchmark.py` lines 203-218 showed `tests/ai/benchmark/test_embedding_benchmark.py:210:sec_cat = InMemoryDocumentTokenizer._infer_category(`, so group 2 changes that test to pass a fixture root.
- `read_file` on `src/devops_cli/ai/benchmark/document_chunker.py` lines 441-448 showed `repo_root: Path | None = None,`, and `read_file` on `src/devops_cli/ai/benchmark/embedding_runner.py` lines 583-587 showed `src/devops_cli/ai/benchmark/embedding_runner.py:585:repo_root=Path.cwd(),`, so `load_test_document_corpus` keeps its signature and that caller needs no change.
- `search_code` for `reset_document_chunker_cache` showed `src/devops_cli/ai/benchmark/document_chunker.py:246:def reset_document_chunker_cache() -> None:` and `tests/conftest.py:80:"devops_cli.ai.benchmark.document_chunker": ("reset_document_chunker_cache",),`, so the name stays and the fixture needs no change.
- `list_files` on `docs`, `docs/guidelines` and `docs/commands` showed the pages of the new domain map, such as `docs/guidelines/kubernetes.md`, `docs/CLUSTER.md`, `docs/DESIGN.md` and `docs/commands/ci.md`, so every path of the map is a file of the commit.
- `read_file` on `src/devops_cli/config/constants.py` lines 5524-5529 gave the constant `CONST_KB_METADATA_TARGET_SUBDIRS` with the value `("devops_cli/libraries", "it_domains/tools", "it_domains/topics")`, and `read_file` on `tests/support/paths.py` lines 20-23 gave `tests/support/paths.py:22:FIXTURES: Final[Path] = TESTS_ROOT / "fixtures"` and `tests/support/paths.py:21:REPO_ROOT: Final[Path] = TESTS_ROOT.parent`, so the JSON gold set is no case path and a behavior group creates it.
- `read_file` on `src/devops_cli/ai/rag/retriever.py` lines 450-465 showed `src/devops_cli/ai/rag/retriever.py:class SemanticRetriever` and `src/devops_cli/ai/rag/retriever.py:457:def search(`, with the keyword arguments `top_k`, `score_threshold` and `collection`, so the scorer adds no ranking code.
- `search_code` showed `tests/support/fakes/qdrant.py:534:def qdrant() -> Iterator[Any]:` and `tests/support/fakes/embeddings.py:94:def embedder() -> Iterator[Any]:`, the two fixtures that install the fake client and the fake embedder.
- The `search` method of `src/devops_cli/ai/rag/retriever.py:class SemanticRetriever` needs a client of Qdrant and an embedding model; `score_gold_set` takes both as arguments and the test installs them through the `qdrant` and `embedder` fixtures.
- `get_knowledge_base_dir` and `list_knowledge_base_articles`, imported at `src/devops_cli/ai/benchmark/document_chunker.py:15:from devops_cli.ai.kb import get_knowledge_base_dir, list_knowledge_base_articles`, need a checkout of the repository; `knowledge_base_source` takes the folder path as an argument, and only the live run reads the checkout.
- `mark_stale_entries` needs a checkout of the repository when its `repo_root` is the repository, which the gold-set test passes as `REPO_ROOT`; the drift test passes a `repo_root` under `tmp_path` and an empty `kb_dir`, so it reads no checkout.
- `load_test_document_corpus`, `document_corpus_paths` and `document_domain_index` need a checkout of the repository as their `repo_root` argument; the new tests pass a root under `tmp_path`, so they read no checkout.
- `docs/TESTING.md:61:A test that agrees code with a committed file reads the file only as the code does at run time, and asserts no value of it.` allows the gold-set test to read the checked-in article through the loader: the test asserts the stale flag of its fixture entry and no value of the article. `tests/gate/tree_checks/config_values.py:85:return not path.endswith(".md") and (` exempts a Markdown document from the config reads, so the article is no config file and no count of `tests/gate/tree_checks/config_reads.toml` changes.
- The new plan answers the finding with `tests/ai/benchmark/test_kb_gold_set.py::test_stale_entry_against_the_checked_in_folder_is_marked`: it loads the checked-in gold set and asserts that its `stale-bandit-version` entry is marked stale with a reason that names `src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md`. The stale marking therefore runs against a checked-in source, and not only against a source that a test writes under `tmp_path`.
- `read_file` on `src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md` lines 1-25 showed `src/devops_cli/ai/knowledge_base/it_domains/tools/bandit.md:3: - "tool:bandit@1.9.*"`, so the article holds no claim that Bandit is pinned to 1.7.5 and the presence check marks that entry stale.
- Every verify is `uv run devops ci test <path>` or `uv run devops ci docs`. The programs are `uv` and `pytest`, both in the runner tool list, and a failure is failure class `test`, which is repaired. The pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`, so a test writes only under `tmp_path`.
- The first checks against the real system are `uv run devops ci test tests/ai/benchmark/test_kb_gold_set.py`, then `uv run devops ci test tests/ai/benchmark/test_embedding_benchmark.py`, then `uv run devops ci test tests/ai/benchmark/test_gold_set_scorer.py`, then `uv run devops ci docs`.
- The live score is recorded by a person, because CI holds no Qdrant and no embedding model: `docs/TESTING.md:73:- **Faked edges**: every program (git, kubectl, helm, minikube, the docker and podman CLIs, the scanners), with the lookup of the program on PATH part of its fake; all network, meaning HTTP on any client stack, raw sockets and DNS;` lists Qdrant and the model and embedding providers as edges that a test fakes.

## Existing Tool Considered

No open, maintained tool covers a labelled gold set with a per-question expected source and stale marking. `ranx` and `ir_measures` compute retrieval metrics but hold no labelled set and no stale marking, and the existing embedding benchmark scores its own sampled tasks over its own corpus. The change builds its own gold set, stale marker, scorer and docs vocabulary: about 25k tokens to build, keep and fix, and about 4 hours. It deletes `_get_domain_knowledge_base_index`, `_DOMAIN_KB_TOPIC_MAP`, `_read_kb_topic_docs`, `_read_architecture_extra_docs` and the three knowledge base reads of `load_test_document_corpus`.

## Dependencies

- Overlaps #5496, which is split from this item: it adds the 62-query project eval set and the paired run comparison beside this gold set, and the gold set and the stale-aware scorer stay here.
- Overlaps #1928, which re-ranks the embedding benchmark with pytrec-eval: this scorer ranks through the retriever seam and changes no benchmark ranking.
- Overlaps #3904, which generates the project digest from its owners at run time: this change scores the digest corpus that the docs directory holds today.
- Overlaps #3917, which drops the knowledge base copies of the project docs: this change removes the knowledge base folder from the benchmark corpus and its vocabulary, and the gold set's articles move with that item.
