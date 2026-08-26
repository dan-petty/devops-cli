"""Documentation generation and validation CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_DOCS_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, write_text_file

app = new_typer(
    help=HELP.docs.app,
    no_args_is_help=True,
)


# =============================================================================
# Helper Utilities
# =============================================================================


def _get_default_docs_dir() -> Path:
    """Find repository docs/ directory."""
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "pyproject.toml").exists():
            return cur / "docs"
        cur = cur.parent
    return Path("docs")


# =============================================================================
# Command: generate
# =============================================================================


@app.command(name="generate")
def generate(
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help=HELP.docs.output_dir,
        ),
    ] = None,
    format_type: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=HELP.options.format_type,
        ),
    ] = DEFAULT_DOCS_FORMAT,
    sync_readme: Annotated[
        bool,
        typer.Option(
            "--sync-readme/--no-sync-readme",
            help=HELP.docs.sync_readme,
        ),
    ] = True,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=HELP.docs.check,
        ),
    ] = False,
) -> None:
    """Generate comprehensive Markdown or JSON documentation for all CLI commands and tools."""
    target_dir = (output_dir or _get_default_docs_dir()).resolve()
    from devops_cli.docs.generator import DocGenerator

    generator = DocGenerator()

    if format_type.lower() == "json":
        json_data = generator.to_json_dict()
        out_json = json.dumps(json_data, indent=2)
        json_file = target_dir / "cli_schema.json"
        if check:
            if not json_file.exists() or json_file.read_text(encoding="utf-8") != out_json:
                print_error(MESSAGES.docs.docs_outdated.format(path=json_file), prefix=False)
                raise typer.Exit(1)
            print_success(MESSAGES.docs.docs_up_to_date, prefix=False)
            return

        if is_dry_run():
            render_dry_run_result(
                command="devops docs generate",
                action="generate_cli_documentation_json",
                target=str(target_dir),
                details={"format": "json", "target_dir": str(target_dir)},
            )
            return

        write_text_file(json_file, out_json)
        print_success(MESSAGES.docs.generated_file.format(path=json_file), prefix=False)
        return

    if format_type.lower() != "markdown":
        print_error(MESSAGES.docs.unsupported_format.format(format=format_type), prefix=False)
        raise typer.Exit(1)

    if check:
        ok, errors = generator.check_docs(target_dir, check_readme_table=sync_readme)
        if not ok:
            for err in errors:
                print_error(err, prefix=False)
            print_error(MESSAGES.docs.check_failed, prefix=False)
            raise typer.Exit(1)
        print_success(MESSAGES.docs.docs_up_to_date, prefix=False)
        return

    if is_dry_run():
        render_dry_run_result(
            command="devops docs generate",
            action="generate_cli_documentation",
            target=str(target_dir),
            details={
                "format": "markdown",
                "sync_readme": sync_readme,
                "target_dir": str(target_dir),
            },
        )
        return

    print_info(
        MESSAGES.docs.generating_docs.format(output_dir=f"[cyan]{target_dir}[/cyan]"), prefix=False
    )
    written = generator.write_all_docs(target_dir, sync_readme_table=sync_readme)
    for path in written:
        print_success(MESSAGES.docs.generated_file.format(path=path), prefix=False)


# =============================================================================
# Command: check
# =============================================================================


@app.command(name="check")
def check(
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help=HELP.docs.output_dir,
        ),
    ] = None,
    check_readme: Annotated[
        bool,
        typer.Option(
            "--check-readme/--no-check-readme",
            help=HELP.docs.sync_readme,
        ),
    ] = True,
) -> None:
    """Check that generated documentation and README.md are up to date with codebase."""
    target_dir = (output_dir or _get_default_docs_dir()).resolve()
    from devops_cli.docs.generator import DocGenerator

    generator = DocGenerator()
    ok, errors = generator.check_docs(target_dir, check_readme_table=check_readme)
    if not ok:
        for err in errors:
            print_error(err, prefix=False)
        print_error(MESSAGES.docs.check_failed, prefix=False)
        raise typer.Exit(1)
    print_success(MESSAGES.docs.docs_up_to_date, prefix=False)


# =============================================================================
# Command: sync-readme
# =============================================================================


@app.command(name="sync-readme")
def sync_readme_cmd(
    readme_path: Annotated[
        Path | None,
        typer.Option(
            "--readme-path",
            "-r",
            help=HELP.docs.readme_path,
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=HELP.docs.check,
        ),
    ] = False,
) -> None:
    """Synchronize the Complete Command Matrix table in README.md with live CLI commands."""
    from devops_cli.docs.generator import DocGenerator

    generator = DocGenerator()
    if check:
        ok, err = generator.check_readme(readme_path)
        if not ok:
            if err:
                print_error(err, prefix=False)
            raise typer.Exit(1)
        print_success(MESSAGES.docs.docs_up_to_date, prefix=False)
        return

    if is_dry_run():
        target = generator._find_readme(readme_path)
        render_dry_run_result(
            command="devops docs sync-readme",
            target=str(target),
            action="sync_readme_matrix",
            details={"readme_path": str(target)},
        )
        return

    target = generator._find_readme(readme_path)
    if generator.sync_readme(readme_path):
        print_success(MESSAGES.docs.synced_readme.format(path=target), prefix=False)
    else:
        print_error(f"Failed to synchronize README Command Matrix in {target}", prefix=False)
        raise typer.Exit(1)
