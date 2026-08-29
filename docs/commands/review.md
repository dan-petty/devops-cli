# `devops review`

AI-powered multi-persona code review and security audits.

## Commands

## `devops review path`

**Review source files directly (no git required).**

```bash
devops review path [OPTIONS] <targets>
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
| `--no-pre-analysis` | `boolean` | - | Disable Stage 1 pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run Stage 1 pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable Stage 2 static security scanning. |
| `--static-scan-only` | `boolean` | - | Run Stage 2 static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable Stage 3 multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run Stage 3 persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable Stage 4 finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run Stage 4 verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable Stage 5 finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run Stage 5 re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable Stage 6 consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run Stage 6 report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

---

## `devops review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops review branch [OPTIONS] <branch_name>
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
| `--no-pre-analysis` | `boolean` | - | Disable Stage 1 pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run Stage 1 pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable Stage 2 static security scanning. |
| `--static-scan-only` | `boolean` | - | Run Stage 2 static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable Stage 3 multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run Stage 3 persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable Stage 4 finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run Stage 4 verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable Stage 5 finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run Stage 5 re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable Stage 6 consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run Stage 6 report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

---

## `devops review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops review pr [OPTIONS] <number>
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
| `--no-pre-analysis` | `boolean` | - | Disable Stage 1 pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run Stage 1 pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable Stage 2 static security scanning. |
| `--static-scan-only` | `boolean` | - | Run Stage 2 static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable Stage 3 multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run Stage 3 persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable Stage 4 finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run Stage 4 verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable Stage 5 finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run Stage 5 re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable Stage 6 consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run Stage 6 report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

---

## `devops review findings`

**Inspect structured findings for a review session.**

```bash
devops review findings [OPTIONS]
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

---

## `devops review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops review verify [OPTIONS] <session>
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

---

## `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

---

## `devops review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset. |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

---

## `devops review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops review apply-patch [OPTIONS] <session>
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

---

## `devops review auto-fix`

**Create a corrective topic branch with verified unit test patch for an approved finding.**

```bash
devops review auto-fix [OPTIONS] <finding_id>
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
