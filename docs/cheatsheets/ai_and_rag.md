# AI and RAG Cheatsheet

This cheatsheet describes how to index and search code and documents with the `devops ai rag` commands.

## Managed Repository Ingestion

The command `devops ai rag ingest` indexes all git repositories configured in `service.repos`.

```bash
# Ingest all repositories configured in service.repos
devops ai rag ingest

# Ingest one or more specific repositories
devops ai rag ingest --repo owner/repo-a --repo owner/repo-b

# Simulate ingestion without network calls or changes
devops ai rag ingest --dry-run
```

### Ingestion Behavior

1. **Preconditions**:
   - `qdrant.url` must be set in configuration or environment.
   - `service.repos` must contain at least one repository.
2. **Removed Repositories**:
   - The command removes projects that are no longer in `service.repos` from the Qdrant vector database and deletes their cached trees.
3. **Incremental Updates**:
   - The command checks the remote `HEAD` commit using `git ls-remote --symref`.
   - If the remote `HEAD` matches the recorded commit and points are intact, the command skips re-indexing.
   - When a commit changes, the command updates a shallow checkout and indexes changed files.
4. **Collection Refill**:
   - If `devops ai rag clear` empties a collection, the next ingestion pass detects missing points and refills all configured repositories.

> [!WARNING]
> Do not index a local working tree under a managed repository name (`<owner>/<name>`). Use `devops ai rag ingest` for managed remote repositories and use `devops ai rag index` for your local workstation projects.

## Visibility and Search Scoping

Repositories can be public or private. The ingestion pass stores the repository visibility in the payload of each code chunk.

- **Unscoped Search**: Queries without `--project` search across public repositories and local workspace code. They automatically exclude private repository chunks.
- **Scoped Search**: Queries with `--project <owner>/<name>` search that repository, including private repositories.

```bash
# Search public repositories and local code (excludes private repositories)
devops ai rag query "database connection pool"

# Search a specific private or public repository
devops ai rag query "database connection pool" --project owner/private-repo
```

## Common Commands

| Command | Purpose |
| :--- | :--- |
| `devops ai rag ingest` | Ingest and index all managed repositories from `service.repos`. |
| `devops ai rag ingest --repo <owner>/<name>` | Ingest a single managed repository. |
| `devops ai rag index [path]` | Index a local workspace or directory into Qdrant. |
| `devops ai rag query <text>` | Search indexed code chunks with semantic similarity. |
| `devops ai rag query <text> --project <name>` | Search code chunks in a specific project. |
| `devops ai rag drift` | Detect staleness between files and the vector index. |
| `devops ai rag status` | Show status of vector collections and point counts. |
| `devops ai rag clear` | Clear vector collections and local index counts. |
