# Code Library: Typer & Click (CLI Command Routing & Option Parsing)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [typer.tiangolo.com](https://typer.tiangolo.com/) • [click.palletsprojects.com](https://click.palletsprojects.com/) |
| **Public Git Repository** | [github.com/tiangolo/typer](https://github.com/tiangolo/typer) • [github.com/pallets/click](https://github.com/pallets/click) |
| **Official PyPI Package** | [pypi.org/project/typer](https://pypi.org/project/typer/) (`0.27.1`) • [pypi.org/project/click](https://pypi.org/project/click/) (`8.4.2`) |
| **DevOps CLI Integration** | [`src/devops_cli/core/cli.py`](file:///workspaces/devops-cli/src/devops_cli/core/cli.py) • [`src/devops_cli/commands/`](file:///workspaces/devops-cli/src/devops_cli/commands/) |

---

## 2. General Information & Architecture

**Typer** is an ergonomic, type-driven library for building command-line applications in Python based on Python 3 type hints. Built directly on top of **Click** (the battle-tested command-line engine from the Pallets project), Typer provides automatic parameter validation, default value assignment, help text formatting, and shell autocompletion (`bash`, `zsh`, `fish`, `powershell`) with zero boilerplate.

In the `devops-cli` ecosystem:
- **CLI Factory Pattern**: `devops_cli.core.cli.new_typer()` instantiates standardized `typer.Typer` apps configured with `no_args_is_help=True`, unified Rich exception handling, and standard parameter resolvers.
- **Centralized Help Catalog**: All option and argument help strings are referenced directly from `devops_cli.lang.HELP` rather than declared as ad-hoc strings in function signatures.
- **Subcommand Hierarchy**: 19 distinct sub-applications (e.g. `devops k8s`, `devops review`, `devops tf`, `devops ci`) are mounted onto the root application via `app.add_typer()`.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Typer + Click |
| :--- | :--- | :--- | :--- |
| **`typer` + `click`** | Type-hint native (`Annotated[T, typer.Option()]`), rich help rendering, nested subcommands, shell completion, mature Click runtime. | Minimal overhead over raw Click; requires type discipline. | **Selected**: Cleanest declarative interface, 100% typing alignment with Pydantic and Python 3.14+, built-in Rich formatting support. |
| **`argparse`** (Stdlib) | Built into standard library, zero dependencies. | Extremely verbose, imperative setup (`parser.add_argument()`), manual sub-parser wiring, brittle type conversion. | Rejected: Too much procedural boilerplate, lacks modern type-hint parsing and Rich terminal styling. |
| **`docopt`** | Command line interface described via POSIX docstrings. | Unmaintained, runtime string regex parsing, no static type checking, poor IDE autocompletion. | Rejected: Incompatible with strict Mypy typing and dynamic language catalog customization. |
| **`fire`** (Google) | Turns any Python object into a CLI automatically. | Hard to control help strings, loose validation, unpredictable nested command discovery. | Rejected: Lacks explicit option contracts and centralized language catalog support. |

---

## 4. Key Concepts & Core Patterns

1. **`Annotated` Type Hints**: Parameters leverage `typing.Annotated[T, typer.Option(...)]` or `typing.Annotated[T, typer.Argument(...)]` to combine static types with runtime metadata.
2. **Subcommand Trees**: Independent domain modules instantiate their own sub-Typer instances which are registered onto the main entry point:
   ```python
   app = new_typer(help=HELP.main.app)
   app.add_typer(k8s_app, name="k8s")
   app.add_typer(review_app, name="review")
   ```
3. **Explicit Context Handling**: Typer callbacks (`@app.callback()`) handle global flags (`--verbose`, `--json`, `--dry-run`) and initialize OpenTelemetry trace headers before command execution.
4. **Defensive Parameter Validation**: Custom validation callbacks enforce semantic constraints (e.g. valid SemVer versions, clean Git identifiers, or existing file paths) before domain execution.

---

## 5. Common & Advanced Usage Examples

### Standard Subcommand with Centralized Help
```python
from pathlib import Path
from typing import Annotated
import typer
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP
from devops_cli.output import print_success

app = new_typer(help=HELP.tf.app, no_args_is_help=True)


@app.command("plan")
def tf_plan_cmd(
    target_dir: Annotated[Path, typer.Argument(help=HELP.tf.target_dir)] = Path("."),
    var_file: Annotated[
        Path | None, typer.Option("--var-file", "-v", help=HELP.tf.var_file)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Generate and show an execution plan for infrastructure changes."""
    ...
```

### Dry-Run Early Return Protocol
```python
from devops_cli.dry_run import is_dry_run, render_dry_run_result

if dry_run or is_dry_run():
    render_dry_run_result(
        command="devops tf plan",
        action="terraform_plan",
        target=str(target_dir),
        details={"var_file": str(var_file) if var_file else None},
    )
    return
```

---

## 6. Best Practices & Security Standards

1. **Never Hardcode Help Strings Inline**: Always import strings from `devops_cli.lang.HELP` to allow localization and maintain 100% documentation consistency.
2. **Explicit Exit Codes**: Always raise `typer.Exit(code)` with standardized exit codes (`0` for success, `1` for general error, `2` for syntax/usage errors).
3. **Redact Sensitive Arguments**: Ensure passwords, secrets, and API tokens use OS Keyring rather than accepting raw tokens via CLI arguments that could be exposed in `/proc` process tables or shell histories.
