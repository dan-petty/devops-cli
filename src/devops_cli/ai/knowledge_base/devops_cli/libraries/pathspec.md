# Code Library: Pathspec (Gitignore & Pattern Matching Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/cpburnz/python-pathspec](https://github.com/cpburnz/python-pathspec) |
| **Public Git Repository** | [github.com/cpburnz/python-pathspec](https://github.com/cpburnz/python-pathspec) |
| **Official PyPI Package** | [pypi.org/project/pathspec](https://pypi.org/project/pathspec/) (`1.1.1`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/diff/`](file:///workspaces/devops-cli/src/devops_cli/ai/diff/) • [`src/devops_cli/commands/review.py`](file:///workspaces/devops-cli/src/devops_cli/commands/review.py) |

---

## 2. General Information & Architecture

**Pathspec** is a Python utility library for pattern matching of file paths based on Git `.gitignore` specification rules (wildcard `*`, directory recursion `**`, negation `!`, and directory anchoring `/`).

In `devops-cli`:
- **Target Repository Filtering**: Excludes ignored build artifacts (`.venv`, `node_modules`, `dist`, `.data`, `.git`) and binary assets from code review passes.
- **Dynamic Gitignore Compilation**: Parses target repository `.gitignore` files dynamically to prevent reviewing files the author explicitly ignored.

---

## 3. Comparable Projects & Tradeoffs

| Matcher | Strengths | Weaknesses | Why `devops-cli` Chose Pathspec |
| :--- | :--- | :--- | :--- |
| **`pathspec`** | Exact Git `.gitignore` compliance, negation (`!`) support, directory recursion (`**`), high performance, pure Python. | Focused purely on path matching. | **Selected**: The canonical standard library used across Black, Flake8, and modern Python tooling for `.gitignore` matching. |
| **`fnmatch`** (Stdlib) | Built into standard library. | Fails on recursive directory matching (`**`), no negation support (`!`), incompatible with `.gitignore` specification. | Rejected: Inaccurate matching of multi-level directory ignores. |
| **`glob`** (Stdlib) | Filesystem traversal and matching. | Interacts directly with disk rather than in-memory path strings, lacks `.gitignore` semantics. | Rejected: Cannot filter in-memory diff paths. |
| **Custom Regex Strings** | Ad-hoc regex construction. | Extremely error-prone, fragile edge cases with path separators on Windows/POSIX. | Rejected: Violates robust parser rules. |

---

## 4. Key Concepts & Core Patterns

1. **`PathSpec.from_lines(pattern_type, lines)`**: Compiles lines of text into a high-speed matcher.
2. **`GitWildMatchPattern`**: The standard gitignore pattern engine.
3. **`spec.match_file(filepath)`**: Returns `True` if the file matches any ignore rule.

---

## 5. Common & Advanced Usage Examples

### Filtering Ignored Files from Git Diff
```python
from pathlib import Path
import pathspec


def filter_ignored_paths(file_paths: list[str], gitignore_content: str) -> list[str]:
    spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_content.splitlines())
    return [p for p in file_paths if not spec.match_file(p)]


# Example usage
all_files = ["src/main.py", ".data/reviews/session.json", "node_modules/pkg/index.js"]
filtered = filter_ignored_paths(all_files, ".data/\nnode_modules/")
assert filtered == ["src/main.py"]
```

---

## 6. Best Practices & Security Standards

1. **Standard POSIX Path Normalization**: Convert Windows `\` backslashes to `/` forward slashes before querying `pathspec`.
2. **Always Ignore Secret Extensions**: Include default safety ignores (`*.key`, `*.pem`, `*.env*`, `.ssh/`) project-wide.
