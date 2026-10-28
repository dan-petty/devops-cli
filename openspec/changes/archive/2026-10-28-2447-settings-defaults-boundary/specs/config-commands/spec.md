## ADDED Requirements

### Requirement: A setting reaches each module that reads it
A module outside `config/` SHALL read a setting from the loaded settings. Where it has no loaded settings, it SHALL read the default that the setting's field declares (`setting_default`). It SHALL NOT read a `DEFAULT_*` name that a settings field takes as its default.

#### Scenario: The chunk size and overlap of the RAG index
- **WHEN** the project config file sets `ai.rag.chunk_size: 900` and `ai.rag.chunk_overlap: 90`, and a `SemanticChunker` is built with no sizes
- **THEN** it splits files by 900 and 90

#### Scenario: The defaults of a RAG search
- **WHEN** `DEVOPS_CLI_AI_RAG_TOP_K` is `9` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD` is `0.6`, and `devops --dry-run ai rag query` runs with no `--top-k` and no `--min-score`
- **THEN** the dry run shows `top_k` 9 and `min_score` 0.6

#### Scenario: A retriever with no defaults
- **WHEN** `DEVOPS_CLI_AI_RAG_TOP_K` is `7` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD` is `0.55`, and a `SemanticRetriever` is built with no defaults
- **THEN** its default top-k is 7 and its default score threshold is 0.55

#### Scenario: The sampling that group analysis records
- **WHEN** the project config file sets `ai.tasks.analysis.temperature: 0.7` and `ai.tasks.analysis.top_p: 0.8`, and group analysis runs with no sampling given
- **THEN** the report records temperature 0.7 and top-p 0.8

#### Scenario: An audit log destination in the configured data directory
- **WHEN** the project config file sets `data.dir`, no `DEVOPS_CLI_DATA_DIR` is set, and `DEVOPS_CLI_AUDIT_LOG_DEST` names a file in that directory
- **THEN** an audit event is written to that file

#### Scenario: The GitHub quota ledger
- **WHEN** `DEVOPS_CLI_DATA_CACHE_DIR` names a directory
- **THEN** the cache directory of each GitHub identity is in that directory

#### Scenario: The state of the roadmap Service
- **WHEN** the project config file sets `data.dir` and no `DEVOPS_CLI_DATA_DIR` is set
- **THEN** the Service keeps its state in `roadmap` under that directory

#### Scenario: The snapshot digest of the OSV database
- **WHEN** `DEVOPS_CLI_DATA_CACHE_DIR` names a directory that holds an `osv_db` database, and the digest is computed with no directory given
- **THEN** the digest is stamped in `osv_db` under that directory
