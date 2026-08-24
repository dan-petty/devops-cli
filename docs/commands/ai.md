# `devops ai`

Configure and test AI providers.

## Commands

## `devops ai config`

**Show or update AI provider configuration.**

```bash
devops ai config [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Provider: ollama, claude, copilot, openai |
| `--model`, `-m` | `string` | - | Model name, e.g. gemma4:26b, claude-opus-4-5 |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated) |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node |
| `--api-base-url` | `string` | - | Override API base URL for any provider |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure |

---

## `devops ai models`

**List available models for the configured provider.**

```bash
devops ai models
```

---

## `devops ai preload`

**Preload configured model into VRAM across all configured Ollama servers.**

```bash
devops ai preload
```

---

## `devops ai test`

**Send a test prompt to verify AI provider connectivity across configured servers.**

```bash
devops ai test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prompt`, `-p` | `string` | `Reply with exactly one word: OK` | Test prompt to send to the provider |
| `--url`, `-u` | `string` | - | Specific Ollama server URL to test |

---

## `devops ai agents`

**Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md).**

```bash
devops ai agents [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Repository root (default: current directory) |
| `--template` | `boolean` | - | Generate from built-in template without calling the LLM |
| `--file`, `-f` | `string` | `['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']` | Files to generate (repeatable) |

---

## `devops ai chat`

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md) |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context |
| `--stream`, `--no-stream` | `boolean` | `True` | Stream response tokens |
| `--tools`, `--no-tools` | `boolean` | `True` | Enable DevOps agent tools |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking |
| `--prewarm`, `--no-prewarm` | `boolean` | `True` | Prewarm the model before starting chat |
| `--explain`, `-e` | `boolean` | - | Explain chat personas, tools, and reasoning modes |

---

## `devops ai bundle-models`

**Bundle Ollama model metadata into tarball for air-gapped DevContainers.**

```bash
devops ai bundle-models [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output directory for model archive bundle |

---

## `devops ai pipeline`

**Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.**

```bash
devops ai pipeline [OPTIONS] <prompt>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<prompt>` | `string` | No | Initial goal or prompt for the multi-agent pipeline |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--personas`, `-p` | `string` | `devsecops,architect,qa` | Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa) |
| `--max-turns` | `integer` | `5` | Maximum tool turns per agent stage |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable reasoning/thinking per agent |

---

## `devops ai review`

**AI-powered multi-persona code review system.**

```bash
devops ai review [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops ai review path`

**Review source files directly (no git required).**

```bash
devops ai review path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory to review |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for files (default: all files) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops ai review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops ai review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base branch to diff against |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--repo` | `path` | `.` | Path to the git repository |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops ai review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops ai review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | owner/repo (default: detected from git remote) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops ai review findings`

**Inspect structured findings for a review session.**

```bash
devops ai review findings [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest) |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED |
| `--unverified` | `boolean` | - | Show unverified findings only |
| `--invalidated` | `boolean` | - | Show invalidated findings only |
| `--verified` | `boolean` | - | Show verified findings only |

### `devops ai review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops ai review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-i` | `integer` | - | 1-based index of the finding to update |
| `--title`, `-t` | `string` | - | Title substring to match finding |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change |

### `devops ai review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops ai review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions |

### `devops ai review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset |
| `--reviews-dir` | `path` | - | Directory containing review sessions |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL |

### `devops ai review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops ai review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Review session ID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | Finding index (1-based) |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively |

---

## `devops ai analyze`

**Analyze codebase metadata and generate structural outlines.**

```bash
devops ai analyze [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

### `devops ai analyze path`

**Analyze a local directory path or single file and save metadata to .data/analysis/.**

```bash
devops ai analyze path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory path to analyze |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for files (default: all files) |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

### `devops ai analyze branch`

**Analyze a git branch diff against base and save metadata to .data/analysis/.**

```bash
devops ai analyze branch [OPTIONS] <branch>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch>` | `string` | No | Branch to analyze (default: active branch) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base branch for diff |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

### `devops ai analyze pr`

**Analyze a GitHub Pull Request and save metadata to .data/analysis/.**

```bash
devops ai analyze pr [OPTIONS] <pr_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pr_number>` | `integer` | Yes | GitHub PR number to analyze |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

---

## `devops ai rag`

**Manage RAG vector embeddings, indexing, and semantic search (Qdrant).**

```bash
devops ai rag [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

### `devops ai rag index`

**Scan and index workspace code and documentation into Qdrant vector database.**

```bash
devops ai rag index [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override |
| `--force`, `-f` | `boolean` | - | Re-index all files ignoring content hash cache |
| `--collection`, `-c` | `string` | - | Target collection override |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

### `devops ai rag query`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag query [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Semantic search query string |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Filter results to a specific project |
| `--language`, `-l` | `string` | - | Filter by programming language |
| `--category` | `string` | - | Filter by category (code, docs, iac, config) |
| `--top-k`, `-k` | `integer` | `5` | Number of results to retrieve |
| `--min-score`, `-s` | `float` | `0.35` | Minimum cosine similarity threshold |
| `--collection`, `-c` | `string` | - | Search only a specific collection |
| `--file`, `-f` | `string` | - | Filter results to a specific file |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

### `devops ai rag status`

**Display status of vector database collections and embedding configurations.**

```bash
devops ai rag status
```

### `devops ai rag reset`

**Alias for clear — clear vector index collections and reset local cache.**

```bash
devops ai rag reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Specific collection to delete (default: all) |
| `--force`, `-f` | `boolean` | - | Bypass confirmation prompt |

### `devops ai rag clear`

**Clear vector index collections from Qdrant.**

```bash
devops ai rag clear [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Specific collection to delete (default: all) |
| `--force`, `-f` | `boolean` | - | Bypass confirmation prompt |

---

## `devops ai benchmark`

**Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.**

```bash
devops ai benchmark [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--models`, `-m` | `string` | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434') |
| `--servers`, `--ollama-urls` | `string` | - | Comma-separated Ollama server URLs for concurrent execution (e.g. 'http://node1:11434,http://node2:11434') |
| `--provider`, `-p` | `string` | - | AI provider (ollama, claude, copilot, openai) |
| `--type`, `--mode` | `string` | `auto` | Benchmark mode: 'auto', 'chat', 'embedding' (default: auto) |
| `--tasks`, `-t` | `string` | - | Filter specific task categories or IDs (e.g. 'security,kubernetes') |
| `--concurrency`, `-c` | `integer` | `4` | Number of concurrent model server workers (default: automatic per model count) |
| `--output`, `-o` | `path` | - | Destination JSON report filepath |
| `--format`, `-f` | `string` | `table` | Output format: table, json, markdown |
| `--dry-run` | `boolean` | - | Simulate benchmark without sending remote LLM requests |
| `--explain`, `-e` | `boolean` | - | Explain benchmark metrics, terminology, and mathematical formulas |
| `--document`, `-d` | `path` | - | Path to large test document for in-memory tokenization and section retrieval |
| `--samples` | `integer` | `5` | Number of random sections to sample for retrieval evaluation |

---
