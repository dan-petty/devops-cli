# rag-index Specification

## Purpose
The workspace indexer of `devops ai rag index`: which files of a directory it embeds into the code and docs collections, and how one index run handles an embedding batch that fails.

## Requirements

### Requirement: The indexer leaves out vendored files
`WorkspaceIndexer.collect_files` SHALL leave out each file that the `.gitattributes` of the working tree set `linguist-vendored` to `set` or `true`. A file marked `linguist-generated` SHALL stay. One `git check-attr` call SHALL read the attributes of all the files of one walk. A directory outside a git work tree SHALL keep all its files.

#### Scenario: A vendored and a generated file
- **WHEN** a git work tree holds `main.py`, `vocab.tiktoken`, `reference.md` and `kept.py`, and its `.gitattributes` holds `*.tiktoken linguist-vendored`, `reference.md linguist-generated` and `kept.py linguist-vendored=false`
- **THEN** the index stores chunks of `main.py`, `reference.md` and `kept.py`, and none of `vocab.tiktoken`

#### Scenario: One git call for all files
- **WHEN** `collect_files` walks a work tree that holds three indexable files
- **THEN** the indexer starts one `git check-attr -z --stdin linguist-vendored`, whose standard input holds the three paths

#### Scenario: A directory with no repository
- **WHEN** `collect_files` walks a directory that no git work tree holds
- **THEN** it starts no `git check-attr`, and it keeps all the files that the other rules keep

### Requirement: An embedding error holds the HTTP status of the reply
An `EmbeddingsError` from a failed request SHALL hold in `status` the HTTP status of the reply, when each endpoint that was asked gave that status. A request with no reply, or endpoints that gave different statuses, SHALL give no status.

#### Scenario: A gateway reply
- **WHEN** the gateway answers an embedding request with HTTP 400, 404, 413, 422 or 503
- **THEN** the error holds that status

#### Scenario: Two Ollama nodes
- **WHEN** one Ollama node answers HTTP 413, and the other node answers HTTP 404 or does not answer
- **THEN** the error holds no status

### Requirement: A transient batch failure gets one more attempt
An embedding batch that fails with a transient error (a timeout, a connect error, a 429 or a 5xx reply) SHALL get one more attempt after a jittered wait through the clock seam.

#### Scenario: The retry succeeds
- **WHEN** the embedder fails the batch of `file_b.py` once with a transient error, and answers the second attempt
- **THEN** the run returns with all three files indexed

### Requirement: A run skips a batch that it cannot embed
The indexer SHALL skip a batch that fails both attempts with a transient error, and a batch whose reply refuses its input with HTTP 400, 413 or 422 after one attempt. It SHALL mark the files of a skipped batch incomplete in the index cache, and SHALL embed the other batches of both collections. A run that stops because the embedding endpoint is not available SHALL embed no later batch.

#### Scenario: One batch fails each try
- **WHEN** three files are indexed one chunk for each batch, and the embedder fails the batch of `file_b.py` on each try with a 504 reply, a 429 reply or a timeout
- **THEN** the run waits once, raises `EmbeddingsError` with exit status 1 whose message names `file_b.py` and the error, and the index holds `file_a.py` and `file_c.py`

#### Scenario: The endpoint refuses the input of one batch
- **WHEN** three files are indexed one chunk for each batch, and the embedder refuses the batch of one file with HTTP 400, 413 or 422
- **THEN** the run sends that batch once, does not wait, raises `EmbeddingsError` with exit status 1 that names the file, and the index holds the two other files

#### Scenario: A skipped code batch does not stop the docs collection
- **WHEN** the run indexes `file_a.py`, `file_b.py` and `guide.md` with one chunk in each batch, and the batch of `file_b.py` times out on each try
- **THEN** the run raises `EmbeddingsError` that names `file_b.py`, the code collection holds `file_a.py`, and the docs collection holds `guide.md`

### Requirement: A run stops when the embedding endpoint is not available
A pybreaker circuit breaker of the run SHALL count the batches in a row that fail each attempt with a transient error. The run SHALL stop when the count gets to 3, or when such a batch comes before any batch of the run got vectors. Before it stops, it SHALL mark the files of that batch incomplete. It SHALL raise `EmbeddingsError` with exit status 1, the last error and each file of the skipped batches. It SHALL send no request for the later batches.

#### Scenario: The endpoint fails the first batch
- **WHEN** the run indexes three files with one chunk in each batch, and the embedder fails each request with a 504 reply, a 429 reply or a timeout
- **THEN** the run sends the batch of `file_a.py` twice and waits once. It stores no point, and raises `EmbeddingsError` with exit status 1 that names `file_a.py` and the error

#### Scenario: Three batches in a row fail
- **WHEN** the run indexes six files with one chunk in each batch, the embedder embeds the batch of `file_a.py`, and it fails each later batch with a 504 reply
- **THEN** the run sends no request for `file_e.py` and `file_f.py`. It raises `EmbeddingsError` with exit status 1 that names `file_b.py`, `file_c.py` and `file_d.py`, and the index holds `file_a.py`

### Requirement: An answered batch sets the count of failed batches to 0
A batch that gets vectors SHALL set the count of failed batches in a row back to 0. A batch whose input the endpoint refuses SHALL also set it back to 0.

#### Scenario: An answered batch sets the count back to 0
- **WHEN** the run indexes seven files with one chunk in each batch, the batches of `file_b.py`, `file_c.py`, `file_e.py` and `file_f.py` fail each try, and the embedder embeds or refuses the batch of `file_d.py`
- **THEN** the run sends the batch of `file_g.py`, and the index holds it

### Requirement: A run with a skipped batch exits 1 at the end
After it saves the cache and the counts, a run that skipped a batch SHALL raise `EmbeddingsError` with exit status 1, the first error, and each file that it did not index. The next run without `--force` SHALL embed those files again.

#### Scenario: The next run embeds the skipped file
- **WHEN** the embedder fails the batch of `file_b.py` on each try, and answers again after that run
- **THEN** a run without `--force` indexes `file_b.py` only

### Requirement: A permanent batch failure ends the run
An embedding batch that fails with a permanent error, such as a refused key (401 or 403), an unserved model (404) or a malformed reply, SHALL end the run at once with `EmbeddingsError`, exit status 1 and the files of the batch, with no retry. A second batch whose input the endpoint refuses before any batch of the run got vectors SHALL also end the run, because the LiteLLM proxy answers an unknown model with HTTP 400.

#### Scenario: The model is not served
- **WHEN** the embedder fails each request with a permanent `EmbeddingsError` of status 401, 403 or 404, or of no status
- **THEN** the run sends one request, and raises `EmbeddingsError` with exit status 1 whose message holds `Failed to embed batch from`

#### Scenario: Two refused batches and no embedded batch
- **WHEN** the embedder refuses each request with HTTP 400
- **THEN** the run sends two requests, stores no point, and raises `EmbeddingsError` with exit status 1 and status 400 whose message names the second batch

### Requirement: Each collection holds a datetime index of indexed_at
`QdrantClient.ensure_collection` SHALL create a payload index for each entry of `CONST_RAG_PAYLOAD_INDEXES` that the payload schema of the collection does not hold, with the schema type of the entry: a tenant `keyword` index on `project_name`, a `keyword` index on `file_path` and on `visibility`, and a `datetime` index on `indexed_at`. It SHALL do this for a new collection and for a collection that exists.

#### Scenario: A new collection
- **WHEN** `ensure_collection("docs", 4)` runs on a store that does not hold `docs`
- **THEN** the client asks for the indexes `project_name` (keyword, tenant), `file_path` (keyword), `visibility` (keyword) and `indexed_at` (datetime), in that order

#### Scenario: A collection with no payload index
- **WHEN** `ensure_collection("docs", 4)` runs on a store whose collection `docs` holds no payload index
- **THEN** the client asks for the same four indexes and does not create the collection again
