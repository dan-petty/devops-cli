# `devops ci`

Run tests, linting, formatting, and type-checks.

## Commands

## `devops ci test`

**Run the test suite, or only the tests covering the given source files.**

Run the test suite, or only the tests covering the given source files.

Passing paths narrows the run to the tests that import or conventionally cover them,
which is what makes this usable as a pre-commit hook on staged files.

```bash
devops ci test [OPTIONS] <paths>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<paths>` | `path` | No | Source or test files to verify. Narrows the run to covering tests; omit to run the full suite. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--verbose`, `-v` | `boolean` | - | Enable detailed logging output. |
| `-k` | `string` | - | Filter tests by keyword expression. |
| `-x` | `boolean` | - | Stop after first failure. |
| `-n`, `--numprocesses` | `string` | - | Number of parallel worker processes. |
| `--fallback` / `--no-fallback` | `boolean` | `True` | Run the full suite when a changed source has no covering tests, rather than reporting success without verifying it. |
| `--repeat` | `integer` | `0` | Run the selected test files N times, one run after another on one process (-n is ignored), each in a shuffled order, with seeds counting up from --seed. 0 runs them once in file order. Refuses the whole suite. |
| `--seed` | `integer` | - | First shuffle seed for --repeat. Defaults to one derived from HEAD's commit hash; has no effect without --repeat. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops ci coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in .data/htmlcov/. |
| `--build-index` | `boolean` | - | Build on-demand coverage reverse index for fast test selection. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops ci lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` / `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops ci format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix` / `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops ci typecheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops ci audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci security`

**Run bandit static security analysis over src/ and tests/, the targets .bandit names.**

```bash
devops ci security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops ci actionlint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci docs`

**Verify (or update with --fix) that documentation is up to date with CLI commands and configuration.**

```bash
devops ci docs [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Synchronize Complete Command Matrix in README.md. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci uv-check`

**Run uv check for fast static type checking and project validation.**

```bash
devops ci uv-check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci lockfile`

**Verify lockfile consistency and freshness via uv lock --check.**

```bash
devops ci lockfile [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci outdated`

**Display outdated dependencies and packages via uv tree --outdated.**

```bash
devops ci outdated [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci devcontainer`

**Validate devcontainer manifest configuration syntax.**

```bash
devops ci devcontainer [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci deps`

**Validate dependency hygiene and imports via deptry.**

```bash
devops ci deps [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci maintain`

**Run automated toolchain, dependency freshness, and lockfile maintenance checks.**

```bash
devops ci maintain [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Automatically synchronize dependencies and lockfile. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci run`

**Run full CI and return a single pass/fail status.**

```bash
devops ci run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` / `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops ci mutate`

**Mutation-test functions with mutmut and show each mutant no test killed; never a gate.**

Mutation-test functions with mutmut and show each mutant no test killed; never a gate.

Each surviving mutant is shown with its diff, then the killed, survived, timeout and no-tests counts. There is no score, and the command exits 0 whatever survives. The first run copies the whole source tree into mutants/, mutates it and runs the test suite once, serially, which can take hours; later runs reuse mutants/ and its test stats. `rm -rf mutants` resets it. If none of the selected functions gives mutmut a mutant, as when their bodies are only `...`, mutmut fails with 'nothing matches'; on a first run, only after the test suite has run.

```bash
devops ci mutate [OPTIONS] <paths>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<paths>` | `path` | No | Source files or directories under src/ to mutate: every function in them, or with --changed only the changed ones. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--changed` | `boolean` | - | Mutate the functions the working tree changed since its merge base with --base, untracked files included unless git ignores them. |
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
