## Context

`src/devops_cli/roadmap/alternatives.py` evaluates `inventory.uses(tool.url, tool.project)` inside `_verdict_of` after ADR confirmation. When `inventory.uses(...)` returns `True`, `_verdict_of` returns `Verdict.IN_USE` with automatic inventory override (`True`). Today `Inventory` (`src/devops_cli/roadmap/inventory.py`) checks:
1. Exact PURL key matches (`_tool_keys(url, project) & self.packages`).
2. Whole-word matches for `_tool_names(url)` inside `self.deployed`.
3. `deps.dev` linked packages (`_linked_packages(project) & self.packages`).

For standard library repositories like `github.com/python/cpython` or `github.com/golang/go`, none of these three checks fire when the repository only holds ecosystem packages such as `pkg:pypi/httpx` or source files such as `.py`.

## Goals / Non-Goals

**Goals:**
- Recognize standard library repositories for languages used in the repository from either SBOM PURL types or deployed file suffixes.
- Short-circuit inside `Inventory.uses` before querying `deps.dev`.
- Keep third-party tools in the same ecosystem unaffected (`covers` stays `covers`).
- Keep repositories with no matching language signal unaffected (`covers` stays `covers`).

**Non-Goals:**
- Running external language classifiers or modifying `ProjectProfile`.
- Querying `deps.dev` or GitHub APIs at runtime for language detection.

## Decisions

1. **Static `_STDLIB_LANGUAGES` table in `inventory.py`**:
   Map canonical `github.com/<owner>/<repo>` project identifiers to `(purl_type, frozenset_of_suffixes)`:
   - `github.com/python/cpython`: `("pypi", frozenset({".py"}))`
   - `github.com/golang/go`: `("golang", frozenset({".go"}))`
   - `github.com/rust-lang/rust`: `("cargo", frozenset({".rs"}))`
   - `github.com/ruby/ruby`: `("gem", frozenset({".rb"}))`
   - `github.com/dotnet/runtime`: `("nuget", frozenset({".cs"}))`
   - `github.com/nodejs/node`: `("npm", frozenset({".js", ".mjs", ".cjs", ".ts"}))`
2. **`suffixes` field on `Inventory`**:
   Extend `_read_files` (or helper `_read_deployed`) to collect lowercased `file.suffix.lower()` alongside the file contents and pass `suffixes` into `Inventory(packages, deployed, suffixes)`. Keep `suffixes: frozenset[str] = frozenset()` defaulted so existing unit tests building `Inventory(packages, deployed)` continue working without changes.
3. **Evaluation order in `Inventory.uses`**:
   Evaluate `_stdlib_in_use(project, self.packages, self.suffixes)` after direct PURL and deployed-word checks and before `if project is None or not self.packages: return False` and `_linked_packages(project)`. Checking before `not self.packages` ensures an empty SBOM with a `.py` deployed file still detects `python/cpython` without calling `deps.dev`.

## Risks / Trade-offs

- If `self.deployed` literally contains the word `"cpython"`, `_tool_names` already matches it as a whole word; testing the empty-signal and deployed-suffix scenarios uses paths/contents without that literal word.
- If a third-party package like `sqlalchemy/sqlalchemy` is evaluated when only `pkg:pypi/httpx` is in the SBOM, it is not in `_STDLIB_LANGUAGES`, so it does not trigger the stdlib rule.
