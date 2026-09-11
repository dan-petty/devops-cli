"""Documentation generation and validation CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from devops_cli.docs.compactor import DocCompactionResult

import typer

from devops_cli.config.constants import (
    CONST_DOCS_DIR_NAME,
    CONST_PYPROJECT_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_DOCS_DIR,
    DEFAULT_DOCS_FORMAT,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result, set_dry_run
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
        if (cur / CONST_PYPROJECT_FILENAME).exists():
            return cur / CONST_DOCS_DIR_NAME
        cur = cur.parent
    return DEFAULT_DOCS_DIR


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


# =============================================================================
# Command: compact
# =============================================================================


def _resolve_compaction_flags(
    roadmap_only: bool, release_notes_only: bool, log_only: bool
) -> tuple[bool, bool, bool]:
    """Determine which doc targets to compact based on user flags."""
    if roadmap_only:
        return True, False, False
    if release_notes_only:
        return False, True, False
    if log_only:
        return False, False, True
    return True, True, True


def _handle_compact_result(result: DocCompactionResult, series: str) -> None:
    """Print user-facing outcome messages for documentation compaction."""
    if not result.modified_files:
        print_success(MESSAGES.docs.compacted_up_to_date.format(series=series), prefix=False)
        return

    print_success(
        MESSAGES.docs.compacted_success.format(series=series, bytes_saved=result.bytes_saved),
        prefix=False,
    )
    for path in result.modified_files:
        print_success(MESSAGES.docs.generated_file.format(path=path), prefix=False)
    if result.archive_file_path:
        print_success(
            MESSAGES.docs.archive_created.format(path=result.archive_file_path),
            prefix=False,
        )


@app.command(name="compact")
def compact_cmd(
    series: Annotated[
        str,
        typer.Option(
            "--series",
            "-s",
            help=HELP.docs.series,
        ),
    ] = "v0.2",
    docs_dir: Annotated[
        Path | None,
        typer.Option(
            "--docs-dir",
            "-d",
            help=HELP.docs.docs_dir,
        ),
    ] = None,
    archive_dir: Annotated[
        Path | None,
        typer.Option(
            "--archive-dir",
            "-a",
            help=HELP.docs.archive_dir,
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=HELP.docs.check_compact,
        ),
    ] = False,
    roadmap_only: Annotated[
        bool,
        typer.Option(
            "--roadmap-only",
            help=HELP.docs.roadmap_only,
        ),
    ] = False,
    release_notes_only: Annotated[
        bool,
        typer.Option(
            "--release-notes-only",
            help=HELP.docs.release_notes_only,
        ),
    ] = False,
    log_only: Annotated[
        bool,
        typer.Option(
            "--log-only",
            help=HELP.docs.log_only,
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help=HELP.main.dry_run,
        ),
    ] = False,
) -> None:
    """Compact historical documentation for completed release series."""
    from devops_cli.docs.compactor import DocCompactor

    target_docs_dir = (docs_dir or _get_default_docs_dir()).resolve()
    target_archive_dir = (archive_dir or (target_docs_dir / "agent" / "archive")).resolve()

    do_roadmap, do_notes, do_log = _resolve_compaction_flags(
        roadmap_only, release_notes_only, log_only
    )
    compactor = DocCompactor()

    if check:
        res = compactor.compact_all(
            docs_dir=target_docs_dir,
            archive_dir=target_archive_dir,
            series=series,
            check=True,
            compact_roadmap=do_roadmap,
            compact_release_notes=do_notes,
            compact_log=do_log,
        )
        if res.modified_files:
            print_error(MESSAGES.docs.compact_check_failed.format(series=series), prefix=False)
            raise typer.Exit(1)
        print_success(MESSAGES.docs.compacted_up_to_date.format(series=series), prefix=False)
        return

    if is_dry_run() or dry_run:
        original_dry_run = is_dry_run()
        set_dry_run(True)
        try:
            res = compactor.compact_all(
                docs_dir=target_docs_dir,
                archive_dir=target_archive_dir,
                series=series,
                dry_run=True,
                compact_roadmap=do_roadmap,
                compact_release_notes=do_notes,
                compact_log=do_log,
            )
            render_dry_run_result(
                command=f"devops docs compact --series {series}",
                action="compact_documentation_series",
                target=str(target_docs_dir),
                details={
                    "series": series,
                    "docs_dir": str(target_docs_dir),
                    "archive_dir": str(target_archive_dir),
                    "bytes_saved": res.bytes_saved,
                    "modified_files": res.modified_files,
                },
            )
            return
        finally:
            set_dry_run(original_dry_run)

    result = compactor.compact_all(
        docs_dir=target_docs_dir,
        archive_dir=target_archive_dir,
        series=series,
        dry_run=False,
        compact_roadmap=do_roadmap,
        compact_release_notes=do_notes,
        compact_log=do_log,
    )
    _handle_compact_result(result, series)
