# Spec Delta

## Purpose

Provides secure persistent caching for LLM responses, ensuring strict directory isolation and preventing malicious traversal attacks.

## ADDED Requirements

### Requirement: Cache keys are validated before file access
The response cache SHALL accept only keys that begin with `llm_` followed by 64 hexadecimal characters. The cache SHALL reject any malformed key before accessing or modifying the filesystem.

#### Scenario: Malformed key rejected
- **WHEN** a caller requests or stores an entry with a key that contains directory traversal sequences or non-hexadecimal characters
- **THEN** the cache rejects the operation without accessing or writing files

### Requirement: Loaded entries must match requested keys
The response cache SHALL verify that loaded entries contain a key identical to the requested key. If the stored key in the file differs from the requested key, the cache SHALL delete the disk file and return no entry.

#### Scenario: Stored key mismatch
- **WHEN** a cached JSON file on disk contains a key that differs from the requested key
- **THEN** the cache deletes the file on disk and returns a cache miss

### Requirement: Cache directory resolves under data directory
The response cache SHALL resolve its storage directory under `<DATA_DIR>/cache/llm`. The configuration `data.dir` and the environment variable `DEVOPS_CLI_DATA_DIR` SHALL determine the cache root.

#### Scenario: Custom data directory configured
- **WHEN** `DEVOPS_CLI_DATA_DIR` is set to an isolated directory
- **THEN** all cache operations and CLI commands read and write inside `<DEVOPS_CLI_DATA_DIR>/cache/llm`

### Requirement: Empty and schema-failing responses are not cached
The AI client SHALL not store responses whose content is empty or contains only whitespace in the cache. The structured client SHALL not store replies that fail schema validation.

#### Scenario: Empty response with thinking block
- **WHEN** a model returns an empty text response containing thinking blocks
- **THEN** the client returns the response to the caller and writes no cache file

#### Scenario: Response fails schema validation
- **WHEN** a structured model response fails Pydantic schema validation on attempt 1
- **THEN** the client deletes any invalid entry at the key and stores no failing reply

### Requirement: Disabled cache clients bypass cache
An AI client configured with disabled caching SHALL neither read nor write the response cache.

#### Scenario: Cache disabled client execution
- **WHEN** an AI client is initialized with `cache_enabled=False`
- **THEN** multiple identical requests dispatch to the provider and create no cache files
