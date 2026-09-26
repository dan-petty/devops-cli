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
| `--provider`, `-p` | `string` | - | Provider: ollama, claude, copilot, openai, gateway |
| `--model`, `-m` | `string` | - | AI model identifier. |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated). |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node. |
| `--api-base-url` | `string` | - | Override the provider's API base URL (provider gateway uses ai.gateway_url). |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file. |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure. |
| `--task`, `-t` | `string` | - | Set these for one task (chat, metadata, analysis, verification, compose, embedding) instead of every AI call. |

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

## `devops ai prewarm`

**Prewarm local models into GPU VRAM or evict idle models across cluster nodes.**

```bash
devops ai prewarm [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | - | Model name to prewarm or evict (defaults to configured AI model). |
| `--keep-alive`, `-k` | `string` | `1h` | Keep-alive duration for loaded model (e.g. 1h, 24h, forever, or 0 for eviction). |
| `--all-nodes`, `-a`, `--single-node` | `boolean` | `True` | Prewarm or evict model across all configured Ollama cluster nodes. |
| `--evict` | `boolean` | - | Evict the model from GPU VRAM immediately (sets keep_alive to 0). |
| `--url`, `-u` | `string` | - | Specific Ollama node URL to target instead of all candidate nodes. |
| `--json` | `boolean` | - | Output results as structured JSON. |

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
| `--model`, `-m` | `string` | - | AI model identifier. |
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
| `--output`, `-o` | `path` | - | Bundle directory; a relative path is a data path under the main worktree, like data.models_dir (default: the configured models directory). |

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
| `--budget`, `-b` | `integer` | `32768` | Max context token budget limit. |
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
| `<spec_path>` | `path` | No | Path to markdown architecture specification contract. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t` | `path` | - | Target source directory to verify or analyze. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops ai repomap`

**Generate compact whole-repository AST symbol and relationship map.**

```bash
devops ai repomap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--max-files`, `-n` | `integer` | `100` | Maximum source files to include. |
| `--include-tests` | `boolean` | - | Include test modules in symbol map. |
| `--multilingual`, `-m` | `boolean` | - | Enable multilingual polyglot scanning across Python, TypeScript, JavaScript, Go, Rust, Java, C#, C, C++, HCL, shell and Markdown. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai audit-library-usage`

**Audit workspace code for library API drift and deprecated calls.**

```bash
devops ai audit-library-usage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--package`, `-p` | `string` | - | Filter by package distribution name. |
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--contracts-dir` | `path` | - | Path to directory containing exported library contract JSON files. |
| `--fail-on-breaking` | `boolean` | - | Exit with code 1 if any breaking API drift issues are detected. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai pack-context`

**Pack and prune source code context to fit token budget while preserving signatures.**

```bash
devops ai pack-context [OPTIONS] <target_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_path>` | `path` | Yes | Path to source code file to pack and prune. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--referenced`, `-r` | `string` | - | Comma-separated list of symbols referenced by caller to prioritize during pruning. |
| `--max-tokens` | `integer` | `<masked>` | Maximum token budget for packed context output. |
| `--strip-private`, `--no-strip-private` | `boolean` | `True` | Strip unreferenced private functions, methods, and attributes. |
| `--skeletonize`, `--no-skeletonize` | `boolean` | `True` | Replace function and method bodies with ellipsis (...) while preserving signatures. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai read`

**Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window).**

```bash
devops ai read [OPTIONS] <target_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_path>` | `path` | Yes | Target file path to read or inspect. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--inspect`, `-i` | `boolean` | - | Enable multi-scale semantic outline and inspection scanner. |
| `--level`, `-l` | `integer` | - | Focal zoom level: 0 (Topology: <200 tokens), 1 (Structural Outline: control flow & signatures), 2 (Deep Focal Window: line slice). |
| `--lines`, `-L` | `string` | - | Line range for Level 2 focal window (e.g. '40:80'). |
| `--symbol`, `-s` | `string` | - | Target symbol name to inspect or focus on. |
| `--format`, `-f` | `string` | `markdown` | Output format: 'text', 'markdown', or 'json'. |
| `--repo`, `-r` | `path` | - | Repository or workspace root directory. |
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
| `<diagram_type>` | `string` | No | Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai prompt-eval`

**Measure the deterministic suppression layer against recorded review verdicts.**

```bash
devops ai prompt-eval [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `devsecops` | Persona whose recorded findings to measure the layer against. |
| `--dataset`, `-d` | `path` | - | Feedback dataset JSONL; a relative path is a data path under the main worktree, like data.feedback_dataset_path (default: the configured feedback dataset). |
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
| `<target_file>` | `path` | Yes | Target source file to synthesize unit tests for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--function`, `-f` | `string` | - | Specific function to synthesize tests for. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai chaos-model`

**Model dependency chaos engineering suite simulating provider faults and validating local failovers.**

```bash
devops ai chaos-model [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mode`, `-m` | `string` | `all` | Chaos fault mode to simulate (latency, rate-limit, timeout, malformed-json, all). |
| `--latency-ms` | `integer` | `500` | Synthetic network latency to inject in milliseconds. |
| `--error-rate` | `float` | `1.0` | Probability of fault injection between 0.0 and 1.0. |
| `--primary-provider` | `string` | `openai` | AI or cloud provider. |
| `--primary-model` | `string` | `gpt-4o` | AI model identifier. |
| `--fallback-provider` | `string` | `ollama` | Fallback AI provider to route execution to upon fault. |
| `--fallback-model` | `string` | `qwen2.5-coder:7b` | Fallback AI model to route execution to upon fault. |
| `--prompt` | `string` | `def test_health(): return True` | Prompt text or workload payload to evaluate. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai quiesce`

**Centralized emergency quiesce cleanly suspending active agent loops and background tasks.**

```bash
devops ai quiesce [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reason`, `-r` | `string` | `Operator requested emergency quiesce` | Reason for constellation quiesce or emergency failover. |
| `--drain-timeout` | `float` | `5.0` | Drain timeout in seconds to wait for in-flight tasks to complete. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai failover`

**Emergency failover controller re-routing tasks to designated fallback endpoints.**

```bash
devops ai failover [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target-provider` | `string` | `ollama` | Fallback AI provider to route execution to upon fault. |
| `--target-model` | `string` | `qwen2.5-coder:7b` | Fallback AI model to route execution to upon fault. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--force` | `boolean` | - | Bypass model capability tier minimum checks during failover. |

---

## `devops ai resume`

**Gracefully resume suspended constellation agent loops and task runners.**

```bash
devops ai resume [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai constellation`

**Display constellation fleet status, active fallback routes, and suspended tasks.**

```bash
devops ai constellation [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

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
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--watch`, `-w` | `boolean` | - | Continuously watch target paths for changes and re-run reviews. |
| `--debounce-ms` | `integer` | `500` | Debounce window in milliseconds for filesystem watcher. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel`, `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire`, `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

### `devops ai review findings`

**Inspect structured findings for a review session.**

```bash
devops ai review findings [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

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

### `devops ai review benchmark`

**Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage.**

```bash
devops ai review benchmark [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | Yes | File(s) or directory(ies) to review on every run; keep them fixed to compare benchmarks. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--runs`, `-n` | `integer` | `3` | Number of reviews to run; the report takes medians across them. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |

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

**Apply suggested LLM code fix for a verified finding.**

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
| `<finding_id>` | `string` | Yes | Finding ID or title to create remediation branch for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `string` | `src/devops_cli/main.py` | Target source file to apply fix to. |
| `--branch`, `-b` | `string` | - | Custom topic branch name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai review corpus`

```bash
devops ai review corpus COMMAND [ARGS]...
```

#### `devops ai review corpus generate`

**Copy source files with one known defect injected into each, and record where.**

```bash
devops ai review corpus generate [OPTIONS] <sources>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sources>` | `path` | Yes | Clean file(s) or directory(ies) to inject defects into; each becomes a folder of the corpus. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--out`, `-o` | `path` | - | Corpus directory to create (default: corpora/\<source\>-\<seed\> under the reviews directory). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--template`, `-t` | `string` | - | Defect template to inject (repeatable; default: all). |

#### `devops ai review corpus score`

**Score a review of a corpus: which injected defects it found, and what verification kept.**

```bash
devops ai review corpus score [OPTIONS] <corpus_dir>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<corpus_dir>` | `path` | Yes | Corpus directory created by `devops review corpus generate`. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Review session to score (default: the latest review of the corpus). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai review samples`

```bash
devops ai review samples COMMAND [ARGS]...
```

#### `devops ai review samples list`

**List the sample catalog, and whether each sample is fetched at its commit.**

```bash
devops ai review samples list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

#### `devops ai review samples fetch`

**Fetch samples at their pinned commits, verifying commit, licence files and paths.**

```bash
devops ai review samples fetch [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to fetch (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

#### `devops ai review samples validate`

**Run devops ai tooling over fetched samples and save a JSON report per category.**

```bash
devops ai review samples validate [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to validate (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--review` | `boolean` | - | Also review each category's synthetic defect corpus and score it (calls the configured LLM). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |

### `devops ai review templates`

```bash
devops ai review templates COMMAND [ARGS]...
```

#### `devops ai review templates list`

**List registered synthetic defect templates and their supported languages.**

```bash
devops ai review templates list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai review templates sweep`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops ai review templates sweep [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save`, `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai review templates check`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops ai review templates check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save`, `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai review hallucinations`

```bash
devops ai review hallucinations COMMAND [ARGS]...
```

#### `devops ai review hallucinations list`

**List catalog entries: builtin ones shipped with the tool, and learned ones from this workspace.**

```bash
devops ai review hallucinations list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--learned` | `boolean` | - | Show learned entries only. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops ai review hallucinations remove`

**Remove learned catalog entries; builtin entries cannot be removed.**

```bash
devops ai review hallucinations remove [OPTIONS] <ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ids>` | `string` | No | Ids of learned entries to remove. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all-learned` | `boolean` | - | Remove every learned entry. |

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

### `devops ai rag drift`

**Detect staleness and drift between the working tree and the Qdrant vector index.**

```bash
devops ai rag drift [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--auto-sync`, `--reindex`, `-s` | `boolean` | - | Automatically re-index stale and newly added files. |
| `--fail-on-drift` | `boolean` | - | Exit with code 1 if index drift or git commit divergence is detected. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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
| `--type`, `--mode` | `string` | `auto` | Benchmark mode: 'auto', 'chat', 'embedding', 'suite'. |
| `--suite` | `boolean` | - | Run multi-model evaluation suite grounded in feedback datasets. |
| `--dataset` | `path` | - | Feedback dataset JSONL for --suite; a relative path is a data path under the main worktree, like data.feedback_dataset_path (default: the configured feedback dataset). |
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

## `devops ai harness`

**Manage agent harness slots, sub-agent local offloading, and tiered synthesis.**

```bash
devops ai harness COMMAND [ARGS]...
```

### `devops ai harness status`

**Display active harness slot configuration, models, and sandboxing status.**

```bash
devops ai harness status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai harness offload`

**Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot.**

```bash
devops ai harness offload [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Path to repository or source directory. |
| `--symbol`, `-s` | `string` | - | Symbol name (class or function) to inspect or search. |
| `--pattern`, `-p` | `string` | - | File glob pattern to scout. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai harness run`

**Execute tiered synthesis: Big decides, small types, big checks.**

```bash
devops ai harness run [OPTIONS] <task>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<task>` | `string` | Yes | Task description to execute via 3-tier synthesis protocol |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Path to repository or source directory. |
| `--symbol`, `-s` | `string` | - | Symbol name (class or function) to inspect or search. |
| `--frontier-model` | `string` | `claude-3-7-sonnet` | Frontier model identifier for architecture and verification. |
| `--local-model` | `string` | `qwen2.5-coder:7b` | Local model identifier for sub-agent offloading. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai ingest`

**Ingest library API contracts, type stubs, and documentation.**

```bash
devops ai ingest COMMAND [ARGS]...
```

### `devops ai ingest library`

**Introspect an installed Python package and extract its public API contract.**

```bash
devops ai ingest library [OPTIONS] <package_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<package_name>` | `string` | Yes | Introspect an installed Python package and extract its public API contract. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--max-depth`, `-d` | `integer` | `1` | Maximum module recursion depth for package introspection. |
| `--output-dir`, `-o` | `path` | - | Directory path for generated output files. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai ingest docs`

**Ingest local or remote documentation into chunked markdown knowledge files.**

```bash
devops ai ingest docs [OPTIONS] <source>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<source>` | `string` | Yes | Ingest local or remote documentation into chunked markdown knowledge files. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Directory path for generated output files. |
| `--max-pages`, `-p` | `integer` | `10` | Maximum number of items to return or display. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai ingest index-libraries`

**Index exported library API contracts into Qdrant vector collection and Valkey cache.**

```bash
devops ai ingest index-libraries [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `.data/libraries` | Path to directory containing exported library contract JSON files. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai ingest query-library`

**Search library contracts and documentation via semantic search or exact symbol lookup.**

```bash
devops ai ingest query-library [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Search library contracts and documentation via semantic search or exact symbol lookup. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--package`, `-p` | `string` | - | Filter by package distribution name. |
| `--exact`, `-e` | `boolean` | - | Perform exact qualified symbol lookup instead of semantic vector search. |
| `--top-k`, `-k` | `integer` | `5` | Maximum number of items to return or display. |
| `--contracts-dir` | `path` | `.data/libraries` | Path to directory containing exported library contract JSON files. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

---

## `devops ai ast`

**Tree-Sitter multilingual AST concrete syntax tree parsing and code graph synthesis.**

```bash
devops ai ast COMMAND [ARGS]...
```

### `devops ai ast parse`

**Parse source file concrete syntax tree and extract structural symbols.**

```bash
devops ai ast parse [OPTIONS] <file_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file_path>` | `path` | Yes | Parse source file concrete syntax tree and extract structural symbols. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--query`, `-q` | `string` | `` | Optional Tree-Sitter S-expression query to execute against the syntax tree. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai ast graph`

**Synthesize whole-repository symbol dependency and reference graph.**

```bash
devops ai ast graph [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--max-files`, `-n` | `integer` | `100` | Maximum source files to include. |
| `--output`, `-o` | `path` | - | Destination file path for output report or artifacts. |
| `--format`, `-f` | `string` | `json` | Output format for synthesized code graph: 'json' or 'dot'. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ai gateway`

**LLM Gateway and distributed inference mesh management.**

```bash
devops ai gateway COMMAND [ARGS]...
```

### `devops ai gateway status`

**Probe LLM Gateway health, latency, and circuit breaker metrics.**

```bash
devops ai gateway status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--provider`, `-p` | `string` | - | Gateway provider: litellm or portkey. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway routes`

**List registered virtual models and target backend inference instances.**

```bash
devops ai gateway routes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--provider`, `-p` | `string` | - | Gateway provider: litellm or portkey. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway failover`

**Trigger or test circuit-breaker failover of a virtual model to secondary backends.**

```bash
devops ai gateway failover [OPTIONS] <virtual_model>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<virtual_model>` | `string` | Yes | Virtual model alias to trigger failover for (devops-chat, devops-coder, devops-reasoning, devops-embedding). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--simulate`, `--no-simulate` | `boolean` | `True` | Simulate failover without altering active routing table. |
| `--force` | `boolean` | - | Bypass model capability tier minimum checks during failover. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway scale`

**Inspect or scale inference backend (vLLM, LightLLM) serving configurations.**

```bash
devops ai gateway scale [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--backend`, `-b` | `string` | `vllm` | Inference backend to scale: vllm or lightllm. |
| `--replicas`, `-r` | `integer` | - | Replica count for backend deployment. |
| `--tensor-parallel-size`, `-tp` | `integer` | - | Tensor Parallelism degree for vLLM (e.g. 2). |
| `--apply`, `--no-apply` | `boolean` | - | Apply replica scale mutation to Kubernetes deployment via kubectl. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway probe-backend`

**Directly probe health and latency of an inference backend.**

```bash
devops ai gateway probe-backend [OPTIONS] <backend>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<backend>` | `string` | Yes | Backend to probe: vllm, lightllm, or ollama. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--backend-url`, `-u` | `string` | - | Optional backend base URL override. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway tune`

**Measure each deployment of a gateway model group and recommend routing weights.**

Measure each deployment of a gateway model group and recommend routing weights.

Each deployment is measured on its own from an ephemeral container attached to the gateway
pod, since the backends admit only the gateway. Read-only: the gateway configuration is not
changed.

```bash
devops ai gateway tune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | `devops-review` | Gateway model group to measure. |
| `--concurrency`, `-c` | `string` | `1,4,8` | Comma-separated concurrency levels to measure. |
| `--rounds` | `integer` | `2` | Requests per worker at each concurrency level. |
| `--prompt-tokens` | `integer` | - | Prompt size in tokens (default: one review page for the analysis task). |
| `--max-tokens` | `integer` | `<masked>` | Completion tokens requested per call. |
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--namespace`, `-n` | `string` | `llm` | Namespace of the gateway deployment. |
| `--deployment` | `string` | `llm-gateway` | Gateway deployment to run the sweep in. |
| `--context` | `string` | - | Kubernetes context override. |
| `--image` | `string` | `python:3.14-slim` | Python image for the sweep container. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai gateway load`

**Report how busy each LLM backend and GPU was over a window, from Prometheus.**

Report how busy each LLM backend and GPU was over a window, from Prometheus.

Mean in flight is the gateway's call seconds per second on each deployment, so it covers the
Ollama nodes too; busy share and queue come from the vLLM servers themselves.

```bash
devops ai gateway load [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--window`, `-w` | `string` | `1h` | How far back to look, e.g. 30m, 2h or 1d. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

---

## `devops ai runs`

**Benchmark and evaluation runs, kept in the data directory and shared through Valkey.**

```bash
devops ai runs COMMAND [ARGS]...
```

### `devops ai runs reindex`

**Rebuild the shared run index in Valkey from the run records in the data directory.**

```bash
devops ai runs reindex [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Only index runs of this mechanism. |

### `devops ai runs connect`

**Find the cluster's run index, check it answers, share runs through it, and index them.**

```bash
devops ai runs connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context` | `string` | - | Kubernetes context (default: current). |
| `--namespace`, `-n` | `string` | `llm` | Namespace of the run index. |
| `--service` | `string` | `valkey-runs` | Service of the run index's Valkey. |
| `--secret` | `string` | `<masked>` | Secret holding the Valkey password. |

### `devops ai runs list`

**List recorded benchmark and evaluation runs.**

```bash
devops ai runs list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Only list runs of this mechanism. |
| `--subject-key`, `-s` | `string` | - | Only list runs matching this subject key or prefix. |
| `--limit`, `-n` | `integer` | `20` | Maximum number of runs to show. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai runs show`

**Show details of a recorded run.**

```bash
devops ai runs show [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID or prefix to show. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai runs compare`

**Compare two runs or a run against its subject's baseline.**

```bash
devops ai runs compare [OPTIONS] <run_a> <run_b>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_a>` | `string` | Yes | First run ID (or current run if second run is omitted). |
| `<run_b>` | `string` | No | Second run ID (optional; defaults to subject baseline). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai runs check`

**Check a run against baseline for regressions past tolerances.**

```bash
devops ai runs check [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID to check against baseline. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--baseline`, `-b` | `string` | - | Override baseline run ID to compare against. |
| `--max-recall-drop` | `float` | `0.0` | Maximum allowable relative drop in recall (e.g. 0.05 for 5%). |
| `--max-duration-increase` | `float` | `0.15` | Maximum allowable relative increase in duration (e.g. 0.15 for 15%). |
| `--max-tokens-increase` | `float` | `<masked>` | Maximum allowable relative increase in prompt tokens (e.g. 0.20 for 20%). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai runs baseline`

```bash
devops ai runs baseline COMMAND [ARGS]...
```

#### `devops ai runs baseline set`

**Set a run as the baseline for its subject.**

```bash
devops ai runs baseline set <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID to designate as baseline. |

#### `devops ai runs baseline list`

**List all configured baselines.**

```bash
devops ai runs baseline list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai runs baseline show`

**Show the baseline for a subject or run.**

```bash
devops ai runs baseline show [OPTIONS] <subject_or_run>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<subject_or_run>` | `string` | Yes | Subject key or run ID to inspect baseline for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Mechanism for subject lookup. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

---

## `devops ai cost`

**Track approximate lifetime spend and manage model pricing.**

```bash
devops ai cost [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, markdown. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai cost report`

**Generate detailed spend and token report across backend services and servers.**

```bash
devops ai cost report [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, prometheus. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai cost prometheus`

**Export AI spend and usage metrics in Prometheus exposition format.**

```bash
devops ai cost prometheus
```

### `devops ai cost update-pricing`

**Synchronize open-source industrial average pricing catalog from remote registry.**

```bash
devops ai cost update-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--source`, `-s` | `string` | - | Custom URL or file path for open-source model pricing dataset. |
| `--timeout`, `-t` | `float` | `15.0` | Request timeout in seconds. |

### `devops ai cost list-pricing`

**List active token pricing rates per model and backend server.**

```bash
devops ai cost list-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--search`, `-s` | `string` | - | Substring or pattern filter for model/endpoint names. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai cost set-price`

**Set custom token pricing override for a model or backend server.**

```bash
devops ai cost set-price <target> <prompt_rate> <completion_rate>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | Yes | Target model identifier or backend server address (e.g. 'qwen2.5-coder:14b', 'localhost:11434'). |
| `<prompt_rate>` | `float` | Yes | Prompt token cost in USD per 1,000,000 tokens. |
| `<completion_rate>` | `float` | Yes | Completion token cost in USD per 1,000,000 tokens. |

### `devops ai cost reset`

**Reset the lifetime AI spend ledger records.**

```bash
devops ai cost reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--yes`, `-y` | `boolean` | - | Confirm deletion of lifetime spend ledger records. |

---

## `devops ai spend`

**Alias for 'cost' command.**

```bash
devops ai spend [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, markdown. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai spend report`

**Generate detailed spend and token report across backend services and servers.**

```bash
devops ai spend report [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, prometheus. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai spend prometheus`

**Export AI spend and usage metrics in Prometheus exposition format.**

```bash
devops ai spend prometheus
```

### `devops ai spend update-pricing`

**Synchronize open-source industrial average pricing catalog from remote registry.**

```bash
devops ai spend update-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--source`, `-s` | `string` | - | Custom URL or file path for open-source model pricing dataset. |
| `--timeout`, `-t` | `float` | `15.0` | Request timeout in seconds. |

### `devops ai spend list-pricing`

**List active token pricing rates per model and backend server.**

```bash
devops ai spend list-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--search`, `-s` | `string` | - | Substring or pattern filter for model/endpoint names. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

### `devops ai spend set-price`

**Set custom token pricing override for a model or backend server.**

```bash
devops ai spend set-price <target> <prompt_rate> <completion_rate>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | Yes | Target model identifier or backend server address (e.g. 'qwen2.5-coder:14b', 'localhost:11434'). |
| `<prompt_rate>` | `float` | Yes | Prompt token cost in USD per 1,000,000 tokens. |
| `<completion_rate>` | `float` | Yes | Completion token cost in USD per 1,000,000 tokens. |

### `devops ai spend reset`

**Reset the lifetime AI spend ledger records.**

```bash
devops ai spend reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--yes`, `-y` | `boolean` | - | Confirm deletion of lifetime spend ledger records. |

---
