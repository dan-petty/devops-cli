## Purpose
The ranking and retrieval scores of the embedding benchmark: how it scores each query against the corpus, which library computes recall, MRR and nDCG, and that the Service image holds the libraries.

## ADDED Requirements

### Requirement: The benchmark ranks with one matrix product
The embedding benchmark SHALL score every query against the whole corpus with one numpy matrix product over row-normalized vectors and MUST NOT call `cosine_similarity` once per chunk.

#### Scenario: Scores match pairwise cosine
- **WHEN** The ranking helper scores a fixed two-query by four-chunk fixture whose vectors are not unit length.
- **THEN** Each score equals the pairwise cosine of that query and chunk within 1e-9, and the matrix product runs once.

#### Scenario: A zero vector scores zero
- **WHEN** A query vector or a chunk vector is all zeros.
- **THEN** Every score with that vector is 0.0 and the run raises no error.

### Requirement: The retrieval metrics come from pytrec_eval
The embedding benchmark SHALL compute recall at 1, 3 and 5, MRR and nDCG at 5 with `pytrec_eval`.

#### Scenario: Metrics match the pure-Python reference
- **WHEN** The metrics helper scores a fixed qrels whose target ranks are 1, 3 and 6.
- **THEN** It returns the same recall at 1, 3 and 5, MRR and nDCG at 5 as the pure-Python reference within 1e-9.

#### Scenario: A target beyond the cut keeps its reciprocal rank
- **WHEN** The target sits at rank 6 and the cut is 5.
- **THEN** Recall at 5 and nDCG at 5 are 0.0, and MRR is one sixth.

### Requirement: The runner holds no private nDCG helper
The embedding runner MUST NOT define `compute_ndcg_at_k` and MUST take every retrieval score from the retrieval metrics module.

#### Scenario: No helper remains
- **WHEN** The source and test trees are searched for the helper name.
- **THEN** No file holds it and the benchmark tests pass.

### Requirement: The runner passes the complexity cap without a suppression
`evaluate_model_on_server` SHALL pass the Ruff C901 check with no `# noqa: C901` marker.

#### Scenario: The complexity check passes
- **WHEN** The Ruff C901 check runs on the benchmark runner.
- **THEN** The check exits 0 and the file holds no suppression marker.

### Requirement: The Service image imports the new libraries
The Service Image smoke test SHALL import numpy and pytrec_eval in the `linux/amd64` image that the pull request builds.

#### Scenario: The smoke test imports both libraries
- **WHEN** The Service Image smoke-test block is read from the two workflow files.
- **THEN** The block runs one python probe that imports numpy and pytrec_eval, and both copies are identical.
