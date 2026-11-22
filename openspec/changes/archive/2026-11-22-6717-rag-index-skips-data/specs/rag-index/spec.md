## Purpose
The workspace indexer of `devops ai rag index`: which files of a directory it embeds into the code and docs collections, and how one index run handles an embedding batch that fails.

## ADDED Requirements

### Requirement: The indexer leaves out generated and vendored files
`WorkspaceIndexer.collect_files` SHALL leave out each file that the `.gitattributes` of the working tree set `linguist-generated` or `linguist-vendored` to `set` or `true`. One `git check-attr` call SHALL read the attributes of all the files of one walk. A directory outside a git work tree SHALL keep all its files.

#### Scenario: A vendored and a generated file
- **WHEN** a git work tree holds `main.py`, `vocab.tiktoken`, `gen.py` and `kept.py`, and its `.gitattributes` holds `*.tiktoken linguist-vendored`, `gen.py linguist-generated=true` and `kept.py linguist-generated=false`
- **THEN** the index stores chunks of `main.py` and `kept.py` only

#### Scenario: One git call for all files
- **WHEN** `collect_files` walks a work tree that holds three indexable files
- **THEN** the indexer starts one `git check-attr -z --stdin linguist-generated linguist-vendored`, whose standard input holds the three paths

#### Scenario: A directory with no repository
- **WHEN** `collect_files` walks a directory that no git work tree holds
- **THEN** it starts no `git check-attr`, and it keeps all the files that the other rules keep

### Requirement: A transient batch failure gets one more attempt
An embedding batch that fails with a transient error SHALL get one more attempt after a jittered wait through the clock seam.

#### Scenario: The retry succeeds
- **WHEN** the embedder fails the batch of `file_b.py` once with a transient error, and answers the second attempt
- **THEN** the run returns with all three files indexed

### Requirement: A run skips a batch that fails both attempts and exits 1 at the end
The indexer SHALL skip a batch that fails both attempts, SHALL mark its files incomplete in the index cache, and SHALL embed the other batches of both collections. After it saves the cache and the counts, the run SHALL raise `EmbeddingsError` with exit status 1, the first error, and each file that it did not index. The next run without `--force` SHALL embed those files again.

#### Scenario: One batch fails each try
- **WHEN** three files are indexed one chunk for each batch, and the embedder fails the batch of `file_b.py` on each try with `Gateway 504 Gateway Timeout`
- **THEN** the run waits once, raises `EmbeddingsError` with exit status 1 whose message names `file_b.py` and `Gateway 504 Gateway Timeout`, and the index holds `file_a.py` and `file_c.py`

#### Scenario: The next run embeds the skipped file
- **WHEN** the embedder answers again after that run
- **THEN** a run without `--force` indexes `file_b.py` only

### Requirement: A permanent batch failure ends the run
An embedding batch that fails with a permanent error, such as an unknown or unserved model, a refused request or a malformed reply, SHALL end the run at once with `EmbeddingsError`, exit status 1 and the files of the batch, with no retry.

#### Scenario: The model is not served
- **WHEN** the embedder fails each request with a permanent `EmbeddingsError`
- **THEN** the run sends one request, and raises `EmbeddingsError` with exit status 1 whose message holds `Failed to embed batch from`
