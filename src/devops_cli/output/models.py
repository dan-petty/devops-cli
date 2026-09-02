"""Pydantic v2 data models for structured CLI outputs, renderable schemas, and console payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table

OutputFormat = Literal["table", "json", "yaml", "yml", "markdown", "raw"]
JustifyMethod = Literal["default", "left", "center", "right", "full"]
MessageLevel = Literal["success", "error", "warning", "info", "muted", "step", "raw"]


class TableColumn(BaseModel):
    """Declarative specification for a structured table column."""

    model_config = ConfigDict(frozen=True)

    header: str
    style: str | None = None
    justify: JustifyMethod = "left"
    width: int | None = None
    no_wrap: bool = False


class TablePayload(BaseModel):
    """Structured Pydantic table definition with header, columns, rows, and borders."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = ""
    columns: list[TableColumn | str | tuple[str, str | int]] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    border_style: str | None = "dim"
    box_style: Any = None
    caption: str | None = None

    @property
    def row_count(self) -> int:
        """Return the number of data rows in the table."""
        return len(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def add_row(self, *items: Any) -> None:
        """Append a data row to the table payload."""
        self.rows.append(list(items))

    def add_column(
        self,
        header: str,
        style: str | None = None,
        justify: JustifyMethod = "left",
        width: int | None = None,
        no_wrap: bool = False,
    ) -> None:
        """Append a column specification to the table payload."""
        self.columns.append(
            TableColumn(
                header=header,
                style=style,
                justify=justify,
                width=width,
                no_wrap=no_wrap,
            )
        )

    def render(self) -> Table:
        """Render this payload into a Rich Table instance."""
        from devops_cli.output.formatter import render_table

        return render_table(
            title=self.title,
            columns=self.columns,
            rows=self.rows,
            border_style=self.border_style,
            box_style=self.box_style,
        )


class KeyValuePayload(BaseModel):
    """Structured Pydantic model for key-value summary presentations."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    items: dict[str, Any] = Field(default_factory=dict)
    key_style: str = "bold cyan"
    value_style: str = "white"

    def to_table_payload(self) -> TablePayload:
        """Convert key-value pairs to a TablePayload instance."""
        rows = [[str(k), str(v)] for k, v in self.items.items()]
        return TablePayload(
            title=self.title,
            columns=[
                TableColumn(header="Property", style=self.key_style),
                TableColumn(header="Value", style=self.value_style),
            ],
            rows=rows,
        )

    def render(self) -> Table:
        """Render key-value table directly."""
        return self.to_table_payload().render()


class StatusBadge(BaseModel):
    """Structured status badge with automated color resolution."""

    model_config = ConfigDict(frozen=True)

    status: str | bool
    label: str | None = None
    ok_color: str = "green"
    fail_color: str = "red"
    warn_color: str = "yellow"

    def render(self) -> str:
        """Render Rich markup status string."""
        from devops_cli.output.formatter import format_status_badge

        return format_status_badge(
            self.status,
            label=self.label,
            ok_color=self.ok_color,
            fail_color=self.fail_color,
            warn_color=self.warn_color,
        )

    def __str__(self) -> str:
        return self.render()


class PanelPayload(BaseModel):
    """Structured Pydantic payload representing a bordered console panel."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: Any = ""
    title: str | None = None
    subtitle: str | None = None
    border_style: str = "cyan"
    expand: bool = True

    def render(self) -> Panel:
        """Render this payload into a Rich Panel instance."""
        from rich.panel import Panel

        rendered_content = (
            self.content.render() if hasattr(self.content, "render") else self.content
        )
        return Panel(
            rendered_content,
            title=self.title,
            subtitle=self.subtitle,
            border_style=self.border_style,
            expand=self.expand,
        )


class MarkdownPayload(BaseModel):
    """Structured Pydantic payload representing markdown text rendering."""

    model_config = ConfigDict(frozen=True)

    content: str
    code_theme: str = "monokai"
    justify: JustifyMethod = "left"

    def render(self) -> Markdown:
        """Render this payload into a Rich Markdown instance."""
        from rich.markdown import Markdown

        return Markdown(
            self.content,
            code_theme=self.code_theme,
            justify=self.justify,
        )


class SyntaxPayload(BaseModel):
    """Structured Pydantic payload representing syntax-highlighted code."""

    model_config = ConfigDict(frozen=True)

    code: str
    language: str = "text"
    theme: str = "monokai"
    line_numbers: bool = False
    start_line: int = 1

    def render(self) -> Syntax:
        """Render this payload into a Rich Syntax instance."""
        from rich.syntax import Syntax

        return Syntax(
            self.code,
            self.language,
            theme=self.theme,
            line_numbers=self.line_numbers,
            start_line=self.start_line,
        )


class RulePayload(BaseModel):
    """Structured Pydantic payload representing a horizontal section rule."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    characters: str = "─"
    style: str = "bold cyan"
    align: Literal["left", "center", "right"] = "center"

    def render(self) -> Rule:
        """Render this payload into a Rich Rule instance."""
        from rich.rule import Rule

        return Rule(
            self.title,
            characters=self.characters,
            style=self.style,
            align=self.align,
        )


class ProgressStep(BaseModel):
    """Structured step update for progressive CLI task execution."""

    model_config = ConfigDict(frozen=True)

    description: str = "Processing..."
    completed: float = 0.0
    total: float = 100.0


class MessagePayload(BaseModel):
    """Structured styled message payload."""

    model_config = ConfigDict(frozen=True)

    message: str
    level: MessageLevel = "info"
    prefix: bool = True


class PrintRequest(BaseModel):
    """Declarative Pydantic request payload for the unified print function."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: Any = ""
    level: MessageLevel = "raw"
    prefix: bool | None = None
    title: str | None = None
    border_style: str | None = None
    highlight: bool = True
    stderr: bool = False
    expand: bool = True


class PrintResult(BaseModel):
    """Structured Pydantic response from a print invocation."""

    model_config = ConfigDict(frozen=True)

    success: bool = True
    level: MessageLevel = "raw"
    stream: Literal["stdout", "stderr"] = "stdout"
    rendered_type: str = "text"


__all__ = [
    "JustifyMethod",
    "KeyValuePayload",
    "MarkdownPayload",
    "MessageLevel",
    "MessagePayload",
    "OutputFormat",
    "PanelPayload",
    "PrintRequest",
    "PrintResult",
    "ProgressStep",
    "RulePayload",
    "StatusBadge",
    "SyntaxPayload",
    "TableColumn",
    "TablePayload",
]
