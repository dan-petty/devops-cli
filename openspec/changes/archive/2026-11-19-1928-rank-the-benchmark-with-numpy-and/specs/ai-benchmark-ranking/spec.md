## Purpose
How the embedding benchmark ranks each query against the corpus and computes its retrieval metrics with numpy and pytrec-eval-terrier, and how the project declares, locks and types those two libraries.

## ADDED Requirements

### Requirement: Numpy ranking
The embedding benchmark SHALL rank each query against the corpus with one numpy matrix product over row-normalized query and corpus vectors, and it MUST NOT call cosine_similarity once for each query and chunk pair.

#### Scenario: Ranking matches pairwise cosine
- **WHEN** The ranking helper scores a fixed fixture of 2 queries and 4 chunks whose vectors are not unit length.
- **THEN** The helper returns the score of each query and chunk pair and the ranked chunk indices of each query, each score equals cosine_similarity for that query and chunk within 1e-9, and the helper makes one matrix product call.

#### Scenario: A zero-norm row keeps a zero score
- **WHEN** The ranking helper scores a fixture that holds one all-zero query vector.
- **THEN** Every score of that query is 0.0 and the helper returns the corpus indices in a fixed order.

### Requirement: Metrics from pytrec_eval
The embedding benchmark SHALL compute recall_at_1, recall_at_3, recall_at_5, mrr and ndcg_at_5 with pytrec_eval over one qrels and one run per evaluation, with the three recalls as percentages.

#### Scenario: Metrics match fixed expected values
- **WHEN** The metrics helper scores a fixed qrels and run whose three targets rank 1, 3 and 6.
- **THEN** It returns recall_at_1 of 100/3 percent, recall_at_3 and recall_at_5 of 200/3 percent, mrr 0.5 and ndcg_at_5 0.5, each within 1e-9.

#### Scenario: A target absent from the corpus scores zero
- **WHEN** The metrics helper scores a run whose target chunk is not in the corpus.
- **THEN** The reciprocal rank and the nDCG of that query are 0.0 and the query still counts in the means.

### Requirement: Remove compute_ndcg_at_k
The source and test trees SHALL hold no `compute_ndcg_at_k` helper and no reference to it, and the benchmark SHALL take nDCG at 5 from pytrec_eval.

#### Scenario: No remaining reference
- **WHEN** The source and test trees are searched for `compute_ndcg_at_k`.
- **THEN** `git grep -n compute_ndcg_at_k -- src tests` finds no match, and the benchmark test suite passes.

### Requirement: Remove C901 marker
The benchmark evaluation function SHALL pass the Ruff C901 check at the cap of 10 with no C901 suppression marker.

#### Scenario: Ruff C901 passes
- **WHEN** The project lint row runs Ruff with C901 and RUF100 over the benchmark module.
- **THEN** The row reports no C901 finding, reports no stale suppression marker, and the module holds no C901 suppression marker.

### Requirement: Dependencies declared
The project SHALL declare numpy and pytrec-eval-terrier as direct runtime dependencies in pyproject.toml and SHALL resolve both in uv.lock, with a linux x86_64 wheel of each.

#### Scenario: Lockfile holds the direct dependencies and their wheels
- **WHEN** The invariant test reads the project manifest and the lock file after the lock is regenerated.
- **THEN** The manifest lists numpy and pytrec-eval-terrier in its dependency list, and the lock holds a resolved package entry for each whose wheel list holds a wheel whose file name ends in .whl and holds linux and x86_64.

### Requirement: Type stub for pytrec_eval
The project SHALL type pytrec_eval with a stub module under typings, SHALL add no mypy override for it, and MUST NOT raise the suppression ceiling for mypy overrides.

#### Scenario: Stub holds the names and no override names the library
- **WHEN** The invariant test reads the project configuration, the stub module and the suppression ceilings.
- **THEN** The configuration holds one mypy override, for statsmodels only, the stub module declares RelevanceEvaluator and evaluate, and the ceiling for mypy overrides is 1.

### Requirement: Service image smoke test imports the libraries
The Service Image check SHALL build the image, and the smoke probe of each workflow SHALL import numpy and pytrec_eval from the installed environment.

#### Scenario: Smoke probe names both imports
- **WHEN** The test reads the smoke step of the ci workflow and of the release workflow.
- **THEN** Each probe names numpy and pytrec_eval, and the two run blocks hold the same text.
