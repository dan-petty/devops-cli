# `devops review`

AI-powered code reviews using expert personas.

## Commands

## `devops review path`

**Review source files directly (no git required).**

```bash
devops review path [OPTIONS] <target>
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

---

## `devops review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops review branch [OPTIONS] <branch_name>
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

---

## `devops review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops review pr [OPTIONS] <number>
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

---

## `devops review findings`

**Inspect structured findings for a review session.**

```bash
devops review findings [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest) |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED |
| `--unverified` | `boolean` | - | Show unverified findings only |
| `--invalidated` | `boolean` | - | Show invalidated findings only |
| `--verified` | `boolean` | - | Show verified findings only |

---

## `devops review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops review verify [OPTIONS] <session>
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

---

## `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions |

---

## `devops review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset |
| `--reviews-dir` | `path` | - | Directory containing review sessions |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL |

---

## `devops review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops review apply-patch [OPTIONS] <session>
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
