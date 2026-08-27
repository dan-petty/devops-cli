# `devops ai`

Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot).

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
| `--model`, `-m` | `string` | - | AI model identifier. |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated). |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node. |
| `--api-base-url` | `string` | - | Override API base URL for any provider. |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file. |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure. |

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
| `--prompt`, `-p` | `string` | `Hello, world!` | Test prompt to send to the provider. |
| `--url`, `-u` | `string` | - | Specific Ollama server URL to test. |

---

## `devops ai agents`

**Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md).**

```bash
devops ai agents [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Repository root directory (default: current directory). |
| `--template` | `boolean` | - | Generate from built-in template without calling the LLM. |
| `--file`, `-f` | `string` | `['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']` | Files to generate (repeatable). |

---

## `devops ai chat`

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa, challenger |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md). |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--stream`, `--no-stream` | `boolean` | `True` | Stream response tokens. |
| `--tools`, `--no-tools` | `boolean` | `True` | Enable DevOps agent tools. |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |
| `--prewarm`, `--no-prewarm` | `boolean` | `True` | Prewarm the model before starting chat. |
| `--explain`, `-e` | `boolean` | - | Explain chat personas, tools, and reasoning modes. |

---

## `devops ai bundle-models`

**Bundle Ollama model metadata into tarball for air-gapped DevContainers.**

```bash
devops ai bundle-models [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Directory path for generated output files. |

---

## `devops ai pipeline`

**Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.**

```bash
devops ai pipeline [OPTIONS] <prompt>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<prompt>` | `string` | No | Initial goal or prompt for the multi-agent pipeline. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--personas`, `-p` | `string` | `devsecops,architect,qa` | Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa). |
| `--max-turns` | `integer` | `5` | Maximum tool turns per agent stage. |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |

---

## `devops ai token-count`

**Calculate exact BPE tokens for text or files using tiktoken context budgeting.**

```bash
devops ai token-count [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | No | File path or text string to calculate tokens for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | `gpt-4o` | AI model identifier. |
| `--budget`, `-b` | `integer` | `8192` | Max context token budget limit. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops ai route`

**Evaluate task complexity and determine the optimal LLM provider and model route.**

```bash
devops ai route [OPTIONS] <task>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<task>` | `string` | Yes | Task name (e.g. review, scan). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tokens`, `-t` | `integer` | `<masked>` | Estimated tokens. |
| `--frontier`, `-f` | `boolean` | - | Force routing to frontier tier models. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops ai spec`

**Verify codebase against executable markdown architecture specification contracts.**

```bash
devops ai spec [OPTIONS] <spec_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<spec_path>` | `path` | No | Path to markdown architecture specification contract |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t` | `path` | - | Target source directory to verify |
| `--dry-run` | `boolean` | - | Simulate architecture spec verification |
| `--json` | `boolean` | - | Output specification verification report as JSON |

---

## `devops ai repomap`

**Generate compact whole-repository AST symbol and relationship map.**

```bash
devops ai repomap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t` | `path` | - | Target root directory to generate symbol map for |
| `--max-files`, `-n` | `integer` | `100` | Maximum source files to include |
| `--include-tests` | `boolean` | - | Include test modules in symbol map |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai diagram`

**Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams.**

```bash
devops ai diagram [OPTIONS] <diagram_type>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<diagram_type>` | `string` | No | Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t` | `path` | - | Target root directory to analyze |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai prompt-eval`

**Benchmark persona prompt variations against verified review feedback datasets.**

```bash
devops ai prompt-eval [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `devsecops` | Review persona to benchmark |
| `--dataset`, `-d` | `path` | - | Path to feedback dataset jsonl |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai test-gen`

**Synthesize isolated pytest unit test suites for functions or source files.**

```bash
devops ai test-gen [OPTIONS] <target_file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_file>` | `path` | Yes | Target source file to synthesize unit tests for |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--function`, `-f` | `string` | - | Specific function to synthesize tests for |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai review`

**AI-powered multi-persona code review system.**

```bash
devops ai review [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |

### `devops ai review path`

**Review source files directly (no git required).**

```bash
devops ai review path [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | No | File(s) or directory(ies) to review. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |

### `devops ai review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops ai review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |

### `devops ai review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops ai review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | Target repository in OWNER/REPO format. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |

### `devops ai review findings`

**Inspect structured findings for a review session.**

```bash
devops ai review findings [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED. |
| `--unverified` | `boolean` | - | Show unverified findings only. |
| `--invalidated` | `boolean` | - | Show invalidated findings only. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

### `devops ai review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops ai review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--index`, `-i` | `integer` | - | 1-based finding index in session to verify. |
| `--title`, `-t` | `string` | - | Match finding by substring in title. |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |

### `devops ai review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops ai review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

### `devops ai review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset. |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

### `devops ai review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops ai review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | 1-based finding index in session to verify. |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively. |

### `devops ai review auto-fix`

**Create a corrective topic branch with verified unit test patch for an approved finding.**

```bash
devops ai review auto-fix [OPTIONS] <finding_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<finding_id>` | `string` | Yes | Finding ID or title to create remediation branch for |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `string` | `src/devops_cli/main.py` | Target source file to apply fix to |
| `--branch`, `-b` | `string` | - | Custom topic branch name |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops ai analyze`

**Analyze codebase metadata and generate structural outlines.**

```bash
devops ai analyze [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

### `devops ai analyze path`

**Analyze all repository files under target path and save metadata to .data/analysis/.**

```bash
devops ai analyze path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory path to analyze. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

### `devops ai analyze branch`

**Analyze a git branch diff against base and save metadata to .data/analysis/.**

```bash
devops ai analyze branch [OPTIONS] <branch>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch>` | `string` | No | Branch to analyze (default: active branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

### `devops ai analyze pr`

**Analyze a GitHub Pull Request and save metadata to .data/analysis/.**

```bash
devops ai analyze pr [OPTIONS] <pr_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pr_number>` | `integer` | Yes | GitHub PR number to analyze. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

---

## `devops ai rag`

**Manage RAG vector embeddings, indexing, and semantic search (Qdrant).**

```bash
devops ai rag [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

### `devops ai rag index`

**Scan and index workspace code and documentation into Qdrant vector database.**

```bash
devops ai rag index [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--include-kb`, `--no-include-kb` | `boolean` | `True` | Include bundled DevOps CLI Knowledge Base in docs collection. |
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

### `devops ai rag index-kb`

**Index the bundled DevOps CLI Knowledge Base into Qdrant for RAG agent retrieval.**

```bash
devops ai rag index-kb [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

### `devops ai rag search`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag search [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Natural language query or code search term. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--language`, `-l` | `string` | - | Filter or target specific programming language. |
| `--category`, `-c` | `string` | - | Filter by category (code, docs, topics, tasks). |
| `--top-k`, `-k` | `integer` | `5` | Number of results to return. |
| `--min-score`, `-s` | `float` | `0.35` | Minimum similarity score (0.0 - 1.0). |
| `--collection` | `string` | - | Target collection override. |
| `--file`, `-f` | `string` | - | Filter by filepath glob pattern. |
| `--explain` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

### `devops ai rag query`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag query [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Natural language query or code search term. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--language`, `-l` | `string` | - | Filter or target specific programming language. |
| `--category`, `-c` | `string` | - | Filter by category (code, docs, topics, tasks). |
| `--top-k`, `-k` | `integer` | `5` | Number of results to return. |
| `--min-score`, `-s` | `float` | `0.35` | Minimum similarity score (0.0 - 1.0). |
| `--collection` | `string` | - | Target collection override. |
| `--file`, `-f` | `string` | - | Filter by filepath glob pattern. |
| `--explain` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

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
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

### `devops ai rag clear`

**Clear vector index collections from Qdrant.**

```bash
devops ai rag clear [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

---

## `devops ai benchmark`

**Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.**

```bash
devops ai benchmark [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--models`, `-m` | `string` | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434'). |
| `--servers`, `--ollama-urls` | `string` | - | Comma-separated Ollama server URLs for concurrent execution (e.g. 'http://node1:11434,http://node2:11434'). |
| `--provider`, `-p` | `string` | - | AI or cloud provider. |
| `--type`, `--mode` | `string` | `auto` | Benchmark mode: 'auto', 'chat', 'embedding'. |
| `--tasks`, `-t` | `string` | - | Filter specific task categories or IDs (e.g. 'security,kubernetes'). |
| `--concurrency`, `-c` | `integer` | `4` | Number of concurrent model server workers (default: automatic per model count). |
| `--output`, `-o` | `path` | - | Destination path for output report or artifacts. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--explain`, `-e` | `boolean` | - | Explain benchmark metrics, terminology, and mathematical formulas. |
| `--document`, `-d` | `path` | - | Path to large test document for in-memory tokenization and section retrieval. |
| `--samples` | `integer` | `5` | Number of random sections to sample for retrieval evaluation. |

---

## `devops ai cache`

**Manage LLM response cache, performance metrics, and warm starting points.**

```bash
devops ai cache COMMAND [ARGS]...
```

### `devops ai cache status`

**Display LLM response cache performance statistics, hit rates, and disk storage.**

```bash
devops ai cache status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai cache clear`

**Purge all in-memory and persistent disk cache entries.**

```bash
devops ai cache clear
```

---
