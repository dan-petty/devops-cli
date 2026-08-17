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

**Send a test prompt to verify AI provider connectivity.**

```bash
devops ai test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prompt`, `-p` | `string` | `Reply with exactly one word: OK` | Test prompt to send to the provider |

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

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md) |
| `--stream`, `--no-stream` | `boolean` | `True` | Stream response tokens |
| `--tools`, `--no-tools` | `boolean` | `True` | Enable DevOps agent tools |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking |

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

**Run a multi-agent Pydantic pipeline with shared DevOps tools.**

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
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable reasoning/thinking per agent |

---

## `devops ai review`

**AI-powered code reviews using expert personas (devsecops, architect, pm, auditor, qa).**

```bash
devops ai review COMMAND [ARGS]...
```

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

**Export invalidated review findings into a JSONL benchmark dataset for prompt tuning.**

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset |
| `--reviews-dir` | `path` | - | Directory containing review sessions |

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

**Analyze codebase metadata and create/update .data/analysis/*-metadata.json files.**

```bash
devops ai analyze COMMAND [ARGS]...
```

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

---
