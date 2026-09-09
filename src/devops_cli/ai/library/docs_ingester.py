"""Multi-source documentation ingester with SSRF egress guardrails.

Ingests local repository documentation or crawled remote reference pages,
normalizes and chunks content by heading hierarchies, and saves structured DocChunks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx2

from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.http.validation import validate_service_url
from devops_cli.models.library import DocChunk, IngestDocResult

_SUPPORTED_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


class _HTMLContentExtractor(HTMLParser):
    """Extract clean markdown and structural headings from HTML, skipping nav/footer/script."""

    IGNORE_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.ignore_depth = 0
        self.page_title = ""
        self.in_title = False
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth > 0:
            return
        if tag_lower == "title":
            self.in_title = True
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_lower[1])
            self.lines.append(f"\n{'#' * level} ")
        elif tag_lower in ("p", "div", "section", "article"):
            self.lines.append("\n")
        elif tag_lower == "li":
            self.lines.append("\n- ")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return
        if self.ignore_depth > 0:
            return
        if tag_lower == "title":
            self.in_title = False
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self.lines.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignore_depth > 0:
            return
        if self.in_title:
            self.page_title += data.strip()
            return
        self.lines.append(data)

    def get_markdown(self) -> tuple[str, str]:
        text = "".join(self.lines).strip()
        return self.page_title, text


def _create_chunk(
    slug: str,
    index: int,
    source: str,
    heading_stack: list[str],
    lines: list[str],
) -> DocChunk | None:
    """Create a DocChunk from accumulated lines."""
    content = "\n".join(lines).strip()
    if not content:
        return None

    title = heading_stack[-1] if heading_stack else slug
    return DocChunk(
        chunk_id=f"{slug}_{index:03d}",
        source=source,
        headings=list(heading_stack),
        title=title,
        content=content,
        token_estimate=max(1, len(content) // 4),
        tags=[slug, "docs"],
    )


def _update_heading_stack(
    stack: list[tuple[int, str]],
    level: int,
    text: str,
) -> list[str]:
    """Update heading stack with new heading level and return flat titles."""
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, text))
    return [h[1] for h in stack]


def _chunk_markdown_content(
    content: str,
    source: str,
    slug: str,
) -> list[DocChunk]:
    """Split markdown text into structured chunks based on heading hierarchy."""
    lines = content.splitlines()
    chunks: list[DocChunk] = []
    heading_stack: list[tuple[int, str]] = []
    flat_headings: list[str] = []
    current_lines: list[str] = []
    chunk_index = 1

    for line in lines:
        match = _HEADING_PATTERN.match(line)
        if match:
            chunk = _create_chunk(slug, chunk_index, source, flat_headings, current_lines)
            if chunk is not None:
                chunks.append(chunk)
                chunk_index += 1
            current_lines = []
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            flat_headings = _update_heading_stack(heading_stack, level, heading_text)
        else:
            current_lines.append(line)

    chunk = _create_chunk(slug, chunk_index, source, flat_headings, current_lines)
    if chunk is not None:
        chunks.append(chunk)

    return chunks


def _save_chunks(chunks: list[DocChunk], output_dir: Path) -> list[str]:
    """Persist doc chunks as JSON files in output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_names: list[str] = []
    for chunk in chunks:
        file_path = output_dir / f"{chunk.chunk_id}.json"
        file_path.write_text(chunk.model_dump_json(indent=2), encoding="utf-8")
        file_names.append(file_path.name)
    return file_names


class DocsIngester:
    """Ingests multi-source documentation from local trees or remote web URLs."""

    def ingest_local_docs(
        self,
        docs_path: Path | str,
        output_dir: Path | str | None = None,
    ) -> IngestDocResult:
        """Ingest markdown and text documentation from a local directory or file."""
        src_path = Path(docs_path)
        if not src_path.exists():
            raise DocsIngestionError(f"Documentation path '{docs_path}' does not exist")

        target_dir = Path(output_dir) if output_dir else Path(".data/docs_ingest") / src_path.stem

        files_to_process: list[Path] = []
        if src_path.is_file():
            files_to_process.append(src_path)
        else:
            for file in src_path.rglob("*"):
                if file.is_file() and file.suffix.lower() in _SUPPORTED_DOC_EXTENSIONS:
                    files_to_process.append(file)

        all_chunks: list[DocChunk] = []
        for file in files_to_process:
            content = file.read_text(encoding="utf-8", errors="replace")
            chunks = _chunk_markdown_content(content, source=str(file), slug=file.stem)
            all_chunks.extend(chunks)

        chunk_files = _save_chunks(all_chunks, target_dir)

        return IngestDocResult(
            source=str(src_path),
            is_remote=False,
            total_pages=len(files_to_process),
            total_chunks=len(all_chunks),
            output_dir=str(target_dir),
            chunk_files=chunk_files,
        )

    def ingest_remote_docs(
        self,
        url: str,
        output_dir: Path | str | None = None,
        max_pages: int = 10,
    ) -> IngestDocResult:
        """Ingest remote documentation page over HTTP/HTTPS with strict SSRF validation."""
        validate_service_url(url, "Docs Ingestion", allow=False)

        parsed = urlparse(url)
        slug = (parsed.path.strip("/").replace("/", "_") or parsed.netloc) or "remote_doc"
        target_dir = Path(output_dir) if output_dir else Path(".data/docs_ingest") / slug

        try:
            with httpx2.Client(timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                raw_text = resp.text
        except Exception as exc:
            raise DocsIngestionError(
                f"Failed to fetch remote documentation from {url}: {exc}"
            ) from exc

        if "html" in content_type:
            parser = _HTMLContentExtractor()
            parser.feed(raw_text)
            _, markdown_text = parser.get_markdown()
        else:
            markdown_text = raw_text

        chunks = _chunk_markdown_content(markdown_text, source=url, slug=slug)
        chunk_files = _save_chunks(chunks, target_dir)

        return IngestDocResult(
            source=url,
            is_remote=True,
            total_pages=1,
            total_chunks=len(chunks),
            output_dir=str(target_dir),
            chunk_files=chunk_files,
        )
