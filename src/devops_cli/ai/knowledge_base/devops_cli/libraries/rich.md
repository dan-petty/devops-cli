# Code Library: Rich (Terminal UI, Tables & Formatting Toolkit)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [rich.readthedocs.io](https://rich.readthedocs.io/) |
| **Public Git Repository** | [github.com/Textualize/rich](https://github.com/Textualize/rich) |
| **Official PyPI Package** | [pypi.org/project/rich](https://pypi.org/project/rich/) (`15.0.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/output/`](file:///workspaces/devops-cli/src/devops_cli/output/) • [`src/devops_cli/ai/review/render.py`](file:///workspaces/devops-cli/src/devops_cli/ai/review/render.py) |

---

## 2. General Information & Architecture

**Rich** is a Python library for writing rich text (with color and style) to the terminal, and for displaying advanced content such as tables, markdown, syntax-highlighted code, tracebacks, progress bars, and status spinners.

In `devops-cli`:
- **Centralized Output Layer**: Direct calls to standard `print()` or `sys.stdout.write()` are restricted in favor of `devops_cli.output` wrappers that respect NO_COLOR, CI modes, and output redirection.
- **Canonical Location Highlighting**: Finding tables render clickable locations using the project-wide standard `filename.ext:n-n` format.
- **Dynamic Spinners**: Long-running background operations (e.g. `devops review`, `devops rag index`, `devops k8s bootstrap`) display non-blocking animated status spinners.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Rich |
| :--- | :--- | :--- | :--- |
| **`rich`** | Beautiful ANSI/TrueColor rendering, Markdown/JSON renderers, structured Table API, spinners, automatic width adjustment, zero legacy baggage. | Slightly higher footprint than raw colorama. | **Selected**: Industry gold standard for terminal developer experiences, seamless integration with Typer and Pydantic. |
| **`colorama`** | Lightweight, simple ANSI cross-platform support on Windows. | Low-level string concatenation, no table formatting, no markdown or syntax trees, no spinners. | Rejected: Requires immense procedural boilerplate to format complex tabular reports. |
| **`tabulate`** | Simple ASCII table formatting. | Limited styling, lacks TrueColor borders, no live status updates, no syntax highlighting. | Rejected: Rich provides vastly superior aesthetic flexibility and color themes. |
| **`curses`** (Stdlib) | Low-level full-screen terminal control. | Complex, platform-specific, takes over entire terminal window (unsuitable for streaming CLI tool outputs). | Rejected: Overkill for CLI command logging and formatted report tables. |

---

## 4. Key Concepts & Core Patterns

1. **Rich Console Singleton**: A single `Console()` instance coordinates all stdout/stderr writes with automatic terminal capability detection.
2. **Table Abstraction**: Declarative table building with explicit column styles, alignments, and borders:
   ```python
   from rich.table import Table

   table = Table(title="Security Findings", border_style="cyan")
   table.add_column("Severity", style="bold red")
   table.add_column("Location", style="cyan")
   table.add_column("Description")
   ```
3. **Status Context Managers**: `console.status("[bold green]Executing AI review...")` displays live spinner animation during blocking operations.
4. **Syntax & Markdown Rendering**: Code snippets and review diffs are rendered with language-specific syntax highlighters.

---

## 5. Common & Advanced Usage Examples

### Standard Table Output
```python
from devops_cli.output import print_table

columns = ["Severity", "Location", "Title", "Fix"]
rows = [
    ["HIGH", "src/auth.py:45-52", "Insecure JWT Secret", "Rotate to OS Keyring"],
    ["MEDIUM", "k8s/deployment.yaml:12-15", "Missing Resource Limits", "Add cpu/mem requests"],
]
print_table(title="Review Findings Summary", columns=columns, rows=rows, border_style="red")
```

### Colorized Status Messages
```python
from devops_cli.output import print_error, print_info, print_muted, print_success, print_warning

print_success("✓ All 10 CI quality gates passed cleanly.")
print_warning("⚠ SSH key expires in 5 days; rotation recommended.")
print_error("✗ Failed to establish connection to Minikube cluster.")
print_muted("Parsing AST symbol tree across 45 source files...")
```

---

## 6. Best Practices & Security Standards

1. **NO_COLOR Compliance**: Always respect the `NO_COLOR` environment variable to support accessibility and plain text piping.
2. **Sanitize Dynamic Strings**: Ensure untrusted user inputs or file contents containing square brackets (`[bold]`) are escaped with `rich.markup.escape()` before being formatted into Rich markup templates.
3. **Canonical Location Links**: Always format file locations as `filename.ext:line` or `filename.ext:start-end` so modern terminal emulators (VS Code, iTerm2, Kitty) make links directly clickable.
