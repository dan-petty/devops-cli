# Design

## Decisions

- **Score two sources with one scorer: the checked-in knowledge base folder and the project digest built from the docs directory and the generated index.**: The issue asks for both scores, and one scorer over the Qdrant client and the embedder that the review loop uses keeps the whole measurement offline.
- **Mark an entry stale by a presence check of its checked-in source and by the drift that `load_matched_kb_manuals` reports for a knowledge base article.**: The drift match is the project's own measure of a manual that no longer applies to the locked versions, and it is deterministic and offline.
- **Keep one deliberately stale entry in the checked-in gold set and assert its marking against the checked-in article in `tests/ai/benchmark/test_kb_gold_set.py`.**: The acceptance criterion needs an entry marked stale on the checked-in folder, and a source that a test writes under `tmp_path` cannot show that the marker reads the repository.
- **Read a checked-in Markdown article in the gold-set test, and no manifest or config file.**: `docs/TESTING.md:61:A test that agrees code with a committed file reads the file only as the code does at run time, and asserts no value of it.` allows the read, and `tests/gate/tree_checks/config_values.py:85:return not path.endswith(".md") and (` exempts a Markdown document from the config reads, so no ratchet count moves.
- **Report hit rate at k=5 and stale share, each a number from 0 to 1, with the counts that make them.**: k=5 is the depth of results that the review loop injects, and the counts let a test assert an exact hit and an exact miss instead of a range.
- **Rank each source's documents through the `search` method of `src/devops_cli/ai/rag/retriever.py:class SemanticRetriever` with `rerank=False`, `hybrid=False` and `score_threshold=0.0`, and count a hit in the top five of that ranked list.**: The benchmark's recall is computed from its own sampled tasks over its own corpus, so it cannot rank another source; the retriever seam already ranks and its tests install the fakes.
- **Keep the gold set as JSON under `tests/fixtures/kb_gold_set/`, and give each entry a `reference` field for the primary web page.**: The fixture root of the tests is `tests/support/paths.py:22:FIXTURES: Final[Path] = TESTS_ROOT / "fixtures"`, and JSON parses with the standard library; the presence check reads the repository path offline and the web page stays a citation.
- **Build the benchmark corpus and its domain vocabulary from `docs/` under the repository root that the caller passes, and never from the bundled folder.**: `src/devops_cli/ai/benchmark/document_chunker.py:395:domain_index = _get_domain_knowledge_base_index()` reads the bundled folder, so the eval task categories would change when the folder is removed, which is the silent change that the issue names.
- **Keep the name `reset_document_chunker_cache` and clear the new domain index cache in it.**: `tests/conftest.py:80:"devops_cli.ai.benchmark.document_chunker": ("reset_document_chunker_cache",),` calls it, so the name stays and the fixture needs no change.
- **Record the live score block in the pull request body from a run in the devcontainer.**: CI holds no Qdrant and no embedding model, so CI checks the offline scorer with the fakes and a person records the live numbers.
- **Assert exact scores in the scorer test: a hit rate at k=5 of 0.5, a stale share of 0.5 and the counts 1 of 2.**: A range of 0 to 1 passes for a scorer that always returns 0.0, so only exact numbers show that the ranking and the stale marking work.

## Rejected alternatives

- **Hard-code the knowledge base folder as the only retrieval source.**: It cannot score the generated digest, and a removal of the folder would change the corpus with no record, which the issue names as the risk.
- **Mark an entry stale only against sources that the test writes under `tmp_path`.**: The acceptance criterion names the checked-in folder, so a source under `tmp_path` leaves the marking untested against the repository; `tests/gate/tree_checks/config_values.py:85:return not path.endswith(".md") and (` exempts a Markdown article from the config-read guard, so the checked-in read is allowed.
- **Keep the domain vocabulary of the eval tasks on the bundled folder while the corpus comes from docs.**: `src/devops_cli/ai/benchmark/document_chunker.py:395:domain_index = _get_domain_knowledge_base_index()` shows that the task categories would still move when the folder is removed, so the corpus change alone would not hold.
- **Call a live Qdrant and a live embedding service from the test.**: `docs/TESTING.md:73:- **Faked edges**: every program (git, kubectl, helm, minikube, the docker and podman CLIs, the scanners), with the lookup of the program on PATH part of its fake; all network, meaning HTTP on any client stack, raw sockets and DNS;` lists Qdrant and the model and embedding providers as edges that a test fakes, and CI has no network.
- **Add `ranx` or `ir_measures` for the metrics.**: The retriever seam already ranks results at a depth, so a new dependency buys nothing for a hit count and a division.
- **Divide the benchmark's recall at five by 100 instead of ranking the source.**: That recall is computed from the benchmark's own sampled tasks over its own corpus, so it says nothing about another source.
- **Mark an entry stale by model judgement.**: The review findings of this repository come from tools and checked facts, not from model output (docs/adr/0005-review-findings-come-from-tools-not-models.md).
- **Keep the gold set in YAML or in a Markdown task prompt.**: The tests read their data under `tests/support/paths.py:22:FIXTURES: Final[Path] = TESTS_ROOT / "fixtures"`, and JSON parses with the standard library, so the loader adds no dependency.
- **Freeze a snapshot of the benchmark corpus.**: A snapshot hides the changes in the docs directory and in the generated index that the corpus must show.
- **Skip the scorer in CI.**: The new scorer would be untested, and the issue asks for a test that scores a source with the fakes.
- **Add a separate vector database for the score.**: The scorer ranks through the retriever that the review loop already uses, so a second store would measure a stack that nothing else runs.
- **Report hit rate at k=1 only, or at k=20.**: k=1 hides a near miss at the depth the loop uses, and k=20 exceeds the five results that the loop injects.

## Unchanged references

- `tests/conftest.py` (caller): The step keeps the name `reset_document_chunker_cache`, so the cache clear in the fixture at line 80 needs no change.
- `tests/ai/benchmark/test_ai_benchmark.py` (test double): It patches `load_test_document_corpus` by name at line 710, and the step keeps that name and its keyword arguments.
- `tests/ai/client/test_ai_client_providers_and_embeddings.py` (caller): It calls `load_test_document_corpus()` with no root at line 181 and asserts only that the corpus is not empty, which the docs corpus keeps true.
