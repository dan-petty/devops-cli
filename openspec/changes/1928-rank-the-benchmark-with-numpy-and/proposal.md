# Proposal

## Why

The embedding benchmark of #1928 ranks every query against every chunk in a pure Python loop, with one cosine_similarity call per pair and its own recall, MRR and nDCG code, so the ranking takes 57 seconds on the 7,699-chunk fixture and about 2 minutes of a 27-to-29-minute run. One numpy matrix product over row-normalized vectors and pytrec_eval give the same scores in under a second.

## What Changes

- Add `src/devops_cli/ai/benchmark/retrieval_metrics.py` with one numpy matrix product over row-normalized query and corpus vectors, and with recall at 1, 3 and 5, MRR and nDCG at 5 from pytrec_eval, the three recalls as percentages.
- Delete compute_ndcg_at_k and the pairwise cosine loop from `src/devops_cli/ai/benchmark/embedding_runner.py`, and take every score from the new module.
- Remove the C901 suppression marker from the benchmark evaluation and keep the function under the cap of 10.
- Declare numpy and pytrec-eval-terrier in `pyproject.toml`, resolve both in `uv.lock`, and map the distribution to the pytrec_eval module in the deptry table.
- Type pytrec_eval with `typings/pytrec_eval.pyi`, in the shape of the existing jq stub, and add no mypy override.
- Add `tests/invariants/test_declared_dependencies.py` to assert the two declared dependencies, their resolved entries in `uv.lock`, a linux x86_64 wheel of each entry, and the names of the stub.
- Update the three test files that import compute_ndcg_at_k or cosine_similarity from the runner, and add the ranking, metrics and no-helper tests.
- Import numpy and pytrec_eval in the Service Image smoke probe of `.github/workflows/ci.yml` and of `.github/workflows/release.yml`, with a test in `tests/commands/test_ci.py` that keeps the two run blocks identical and holds both imports.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-benchmark-ranking`: Numpy ranking, Metrics from pytrec_eval, Remove compute_ndcg_at_k, Remove C901 marker, Dependencies declared, Type stub for pytrec_eval, Service image smoke test imports the libraries

### Modified Capabilities

None.

## Impact

- Code: `pyproject.toml`, `uv.lock`, `typings/pytrec_eval.pyi`, `src/devops_cli/ai/benchmark/retrieval_metrics.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Tests: `tests/invariants/test_declared_dependencies.py`, `tests/ai/benchmark/test_retrieval_metrics.py`, `tests/ai/benchmark/test_ai_benchmark.py`, `tests/ai/benchmark/test_embedding_benchmark.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`, `tests/commands/test_ci.py`

## Feasibility

- The probe lines of the staging commit, quoted word for word: ``The path `src/devops_cli/ai/benchmark/embedding_runner.py` is a file of the staging commit.``
- The probe lines of the staging commit, quoted word for word: ``The path `typings/jq.pyi` is a file of the staging commit.``
- The probe lines of the staging commit, quoted word for word: ``The path `typings/pytrec_eval.pyi` is no file of the staging commit. No commit in the history deleted or renamed it.``
- The probe lines of the staging commit, quoted word for word: ``The path `retrieval_metrics.py` is no file of the staging commit. No commit in the history deleted or renamed it.``
- The probe lines of the staging commit, quoted word for word: ``The path `.data/agent/scratch/481a-numpy-ranking.patch` is no file of the staging commit. No commit in the history deleted or renamed it.``
- The premise holds: the benchmark module is a file of the staging commit, and `src/devops_cli/ai/benchmark/retrieval_metrics.py`, `typings/pytrec_eval.pyi` and `tests/invariants/test_declared_dependencies.py` are files that the change creates, so no probe line shows a false premise.
- read_file of `src/devops_cli/ai/benchmark/embedding_runner.py` showed the helper that the change removes at `src/devops_cli/ai/benchmark/embedding_runner.py:69:def compute_ndcg_at_k(ranked_indices: list[int], target_idx: int, k: int = 5) -> float:`, its call at `src/devops_cli/ai/benchmark/embedding_runner.py:466:ndcg = compute_ndcg_at_k(ranked_indices, target_idx, k=5)`, the per-pair loop at `src/devops_cli/ai/benchmark/embedding_runner.py:443:for idx, (eval_item, q_vec) in enumerate(zip(pairs, query_vectors, strict=False)):`, the call at `src/devops_cli/ai/benchmark/embedding_runner.py:449:sim = cosine_similarity(q_vec, c_vec)` and the marker at `src/devops_cli/ai/benchmark/embedding_runner.py:350:def evaluate_model_on_server( # noqa: C901`, so the loop and the suppression that the issue names are there.
- references compute_ndcg_at_k answered 'files 4, lines 14': `src/devops_cli/ai/benchmark/embedding_runner.py` 2, `tests/ai/benchmark/test_ai_benchmark.py` 5, `tests/ai/benchmark/test_embedding_benchmark.py` 5, `tests/ai/client/test_ai_client_providers_and_embeddings.py` 2. Each of the four files is in the changes of the group that removes the helper.
- references cosine_similarity answered 'files 8, lines 29': `src/devops_cli/ai/benchmark/embedding_runner.py` 2, `src/devops_cli/ai/vector_similarity.py` 2, `src/devops_cli/roadmap/nearest.py` 3, `tests/ai/benchmark/test_ai_benchmark.py` 7, `tests/ai/benchmark/test_embedding_benchmark.py` 8, `tests/ai/client/test_ai_client_providers_and_embeddings.py` 3, `tests/support/fakes/qdrant.py` 2, and one archived proposal under `openspec/changes/archive/`. The group that removes the helper changes the runner and the three test files; the definition, `src/devops_cli/roadmap/nearest.py` and the fake stay, as a decision says.
- read_file of `tests/support/fakes/qdrant.py` showed `tests/support/fakes/qdrant.py:25:def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:` and its own call at `tests/support/fakes/qdrant.py:194:sim = _cosine_similarity(query_vector, p.get("vector", []))`, so that hit is a local helper of the fake and no import of the shared function; the reference entry says so.
- read_file of `pyproject.toml` showed the dependency list at `pyproject.toml:11:dependencies = [`, the stub path at `pyproject.toml:205:mypy_path = "typings"`, the single override at `pyproject.toml:209:[[tool.mypy.overrides]]`, the lint selection at `pyproject.toml:160:"C901", "PLR1702", "PGH004", "PGH003", "RUF100", "SIM115", "PT011", "PT015", "PT017", "PT018",`, the complexity cap at `pyproject.toml:175:max-complexity = 10`, and the deptry table at `pyproject.toml:349:[tool.deptry.per_rule_ignores]`, so the lint row reports a function over the cap and a stale marker, and a deptry map belongs above that table.
- read_file of `tests/invariants/test_architectural_invariants.py` showed the ceiling at `tests/invariants/test_architectural_invariants.py:144:"[[tool.mypy.overrides]]": 1,` and the marker ceiling at `tests/invariants/test_architectural_invariants.py:120:DEFAULT_C901_SUPPRESSION_CEILING: int = 25`, so a second override fails the ceiling test and a removed marker only lowers a count.
- read_file of `uv.lock` showed numpy locked as a transitive package at `uv.lock:2571:name = "numpy"` and `uv.lock:2572:version = "2.5.4"`, with a linux x86_64 wheel at `uv.lock:2581:numpy-2.5.4-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`, so this change is what declares numpy and the lock already shows the shape of the wheel entry that the new test asserts.
- search_code for `pytrec` answered 'No match', so no file of the staging commit names the library and `uv.lock` holds no entry for it yet: the lock run of the first group adds the entry, and the invariant test of that group asserts its resolved version and a linux x86_64 wheel, which is the wheel criterion of the issue.
- read_file of `src/devops_cli/ai/vector_similarity.py` showed the zero-norm guard at `src/devops_cli/ai/vector_similarity.py:18:if norm_a == 0.0 or norm_b == 0.0:` and the division at `src/devops_cli/ai/vector_similarity.py:20:return float(dot / (norm_a * norm_b))`, so a raw dot product would change every score.
- read_file of `tests/ai/benchmark/test_embedding_benchmark.py` showed `tests/ai/benchmark/test_embedding_benchmark.py:18:cosine_similarity,` inside an import from the runner, and read_file of `tests/ai/benchmark/test_ai_benchmark.py` showed the same import block at `tests/ai/benchmark/test_ai_benchmark.py:589:compute_ndcg_at_k,` and `tests/ai/benchmark/test_ai_benchmark.py:590:cosine_similarity,`, so both tests break when the runner stops exporting the two names.
- read_file of `src/devops_cli/models/benchmark.py` showed `src/devops_cli/models/benchmark.py:148:recall_at_1: float = Field(default=0.0, ge=0.0, le=100.0)`, so every recall field of the report is a percentage.
- read_file of `src/devops_cli/commands/ci.py` showed the lockfile row at `src/devops_cli/commands/ci.py:898:cmd=["uv", "lock", "--check"],` and the deps row at `src/devops_cli/commands/ci.py:919:cmd=["uv", "run", "deptry", "src"],`, so the gate re-checks the lock that the first group writes.
- search_code for `Run Service Image Smoke Test` answered six lines: the step name in `.github/workflows/ci.yml` and in `.github/workflows/release.yml`, and four lines of `tests/commands/test_ci.py`. The set of smoke steps therefore has two members, and this plan decides both: the group that changes the workflows edits both run blocks to the same text and runs that test file as its verify.
- read_file of the service-image job of `.github/workflows/ci.yml` and of `.github/workflows/release.yml` showed the same probe command in both, at `.github/workflows/ci.yml:489:import getpass, pathlib, subprocess;` and at `.github/workflows/release.yml:388:import getpass, pathlib, subprocess;`, so the group writes the two imports once and copies the same text into both run blocks.
- read_file of `tests/commands/test_ci.py` showed the parity assertion at `tests/commands/test_ci.py:1518:ci_run == rel_run,` inside `tests/commands/test_ci.py:1496:def test_service_image_smoke_test_parity() -> None:`, so an edit of one workflow run block alone breaks that test; the workflow group changes both workflows in one group and adds its import test to that file.
- read_spec of `ai-benchmark` gave the purpose 'The servers that `devops ai benchmark` and its MCP tool `ai_benchmark` send requests to, and the part that a caller has in choosing them.' The ranking, its metrics, the two libraries and their typing are another subject, so the delta adds the capability ai-benchmark-ranking.
- list_files of `src/devops_cli/ai/benchmark` showed ten modules and no retrieval_metrics.py, and list_files of `tests/invariants` showed no test_declared_dependencies.py, while search_code for `test_declared_dependencies` answered 'No match'; both files are created by this change.
- find_issues for `pytrec_eval` answered `#1928 open refactor(ai): rank the benchmark with numpy and pytrec-eval`, `#3902 open test(ai): a gold set measures retrieval of knowledge base facts` and `#4961 open feat(ai): track embedding and reranking serving for retrieval`. The bodies of #3902 and #4961 build a gold set and a serving study, and neither changes a file of this plan, so no item comes first.
- The rejected plan of #5140 is answered: the first group adds `typings/pytrec_eval.pyi`, adds no `[[tool.mypy.overrides]]` entry, and keeps the ceiling at 1; the spec delta holds the requirement 'Dependencies declared'; and the new invariant test reads `pyproject.toml`, `uv.lock` and the stub, so the stub is named by a command and not only by the text.
- The lockfile criterion of the issue, 'uv.lock holds a resolved version and a linux/amd64 wheel for each', is delivered by the first group: its invariant test asserts a resolved package entry for numpy and for pytrec-eval-terrier and a wheel of each entry whose file name holds `linux` and `x86_64`, and the scenario 'Lockfile holds the direct dependencies' states the same check, so no library is left to a person.
- The scenario 'No remaining reference' names compute_ndcg_at_k, and the group that removes the helper writes the case `tests/ai/benchmark/test_embedding_benchmark.py::test_benchmark_module_defines_no_compute_ndcg_at_k` first, so that scenario has a behavior test that names the removed helper.
- The scenario 'Ranking matches pairwise cosine' names cosine_similarity, and the group that adds the module writes `tests/ai/benchmark/test_retrieval_metrics.py::test_ranking_matches_cosine_similarity_in_one_matmul` first, so the name is in the test of a behavior group.
- The first checks that the implementation runs against the real system: `uv lock` in the first group, then `uv run devops ci test tests/invariants/test_declared_dependencies.py`, then `uv run devops ci test tests/ai/benchmark/test_retrieval_metrics.py`, then `uv run devops ci test tests/commands/test_ci.py`, and `uv run devops ci --check --only lint` after the marker goes.
- Precondition of `uv lock`: a network, to resolve numpy and pytrec-eval-terrier from the package index and to rewrite `uv.lock`.
- Precondition of `uv run devops ci test`: a checkout of the repository, and a network on the first run, which installs the two libraries into the environment.
- Precondition of `uv run devops ci --check --only lint`: a checkout of the repository, and no network.
- The plan introduces three verify programs: the pytest module `tests/invariants/test_declared_dependencies.py`, the pytest module `tests/ai/benchmark/test_retrieval_metrics.py`, and the new case in `tests/commands/test_ci.py`. Each runs under the pytest and python of the runner image, which the runner tools list holds, and each reads only files of the checkout, so none needs a client, a cluster or a network; `ruff` and `deptry` are runner tools too. The pod settings stay as they are: runAsNonRoot, readOnlyRootFilesystem, capabilities dropped, no privilege escalation, seccompProfile RuntimeDefault.
- Failure classes: a fault of the ranking or of the runner stops with class test, a lint fault with class lint, a fault of the stub with class types, a lock that does not resolve or a lock entry without a linux x86_64 wheel with class test in the invariant module, and a smoke probe that drifts from its twin with class test in `tests/commands/test_ci.py`. The verifies start no program outside the runner tools uv, python, pytest, ruff and deptry.
- not checked: the 57-second and 0.7-second timings, the 17,623-chunk run and the 962 tests of the patch, which only the issue body records, because this run ran no benchmark. not checked: the licence, the advisory state and the wheel set of pytrec-eval-terrier, because no tool of this run reaches the package index; the issue states the Python 3.14 x86_64 wheel, and the invariant test asserts the wheel in the lock once the lock resolves it.
- The change removes only the ranking time: the corpus embedding, at 19 to 24 minutes of the run, is untouched, so about 2 minutes of a 27-to-29-minute run is what this plan saves.

## Existing Tool Considered

pytrec-eval-terrier, imported as pytrec_eval, computes recall, MRR and nDCG, and numpy computes the matrix product; the issue records that the library is maintained, MIT licensed and free of advisories. The change builds neither and adopts both.

## Dependencies

None.
