# `devops release`

Manage release cycles, version bumping, changelogs, and release verification.

## Commands

## `devops release status`

**Display current release status, versions, tags, changelog, and docs state.**

```bash
devops release status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## `devops release prepare`

**Bump version across pyproject.toml and source, update changelog, and sync docs.**

```bash
devops release prepare [OPTIONS] <version>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<version>` | `string` | Yes | Target semantic version (e.g., 0.1.8) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--sync-docs`, `--no-sync-docs` | `boolean` | `True` | Regenerate CLI reference docs and sync README matrix |
| `--changelog`, `--no-changelog` | `boolean` | `True` | Ensure CHANGELOG.md contains release header with current date |
| `--create-pr`, `-p` | `boolean` | - | Create release branch, commit changes, and open a GitHub Release PR |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## `devops release pr`

**Create release branch, commit version bumps, and open a GitHub Release Pull Request.**

```bash
devops release pr [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target release version (defaults to pyproject.toml) |
| `--base`, `-b` | `string` | `main` | Target base branch for Pull Request |
| `--draft` | `boolean` | - | Create Pull Request as a draft |
| `--labels`, `-l` | `string` | `release` | Comma-separated labels to attach to PR |
| `--push`, `--no-push` | `boolean` | `True` | Push release branch to origin |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## `devops release check`

**Verify release readiness (version consistency, docs freshness, and CI quality gates).**

```bash
devops release check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--skip-ci` | `boolean` | - | Skip running the 7-gate CI test suite |
| `--allow-dirty` | `boolean` | - | Allow uncommitted changes in git repository |
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## `devops release notes`

**Print markdown release notes for a specified or current release version.**

```bash
devops release notes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Release version to extract notes for |
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## `devops release tag`

**Create release commit and annotated git tag.**

```bash
devops release tag [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Release version (defaults to pyproject.toml) |
| `--push`, `-p` | `boolean` | - | Push release commit and git tag to origin |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--message`, `-m` | `string` | - | Custom tag annotation message |
| `--root`, `-r` | `path` | - | Project repository root directory |

---
