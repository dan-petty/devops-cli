"""Multi-source documentation ingester with SSRF egress guardrails.

Ingests local repository documentation or crawled remote reference pages,
normalizes and chunks content by heading hierarchies, and saves structured DocChunks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx2

from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.http.validation import validate_service_url
from devops_cli.models.library import DocChunk, IngestDocResult
from devops_cli.security.sanitizer import mask_uri_credentials

_SUPPORTED_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


def _extract_hrefs(attrs: list[tuple[str, str | None]]) -> list[str]:
    return [val for name, val in attrs if name.lower() == "href" and val]


def _format_starttag(tag_lower: str) -> str | None:
    if tag_lower in ("p", "div", "section", "article"):
        return "\n"
    if tag_lower == "li":
        return "\n- "
    if len(tag_lower) == 2 and tag_lower[0] == "h" and tag_lower[1].isdigit():
        return f"\n{'#' * int(tag_lower[1])} "
    return None


class _HTMLContentExtractor(HTMLParser):
    """Extract clean markdown and structural headings from HTML, skipping nav/footer/script."""

    IGNORE_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.ignore_depth = 0
        self.page_title = ""
        self.in_title = False
        self.lines: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth > 0:
            return
        if tag_lower == "title":
            self.in_title = True
            return
        if tag_lower == "a":
            self.links.extend(_extract_hrefs(attrs))
            return
        prefix = _format_starttag(tag_lower)
        if prefix:
            self.lines.append(prefix)

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
            return
        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self.lines.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignore_depth > 0:
            return
        if self.in_title:
            self.page_title += data.strip()
            return
        self.lines.append(data)

    def get_markdown(self) -> tuple[str, str, list[str]]:
        text = "".join(self.lines).strip()
        return self.page_title, text, self.links


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
            rel = file.relative_to(src_path) if not src_path.is_file() else Path(file.name)
            slug = (
                re.sub(r"[^a-zA-Z0-9_-]+", "_", str(rel.with_suffix("")).replace("/", "_")).strip(
                    "_"
                )
                or file.stem
            )
            chunks = _chunk_markdown_content(content, source=str(file), slug=slug)
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

        parsed_origin = urlparse(url)
        origin_netloc = parsed_origin.netloc
        base_slug = (
            parsed_origin.path.strip("/").replace("/", "_") or parsed_origin.netloc
        ) or "remote_doc"
        target_dir = Path(output_dir) if output_dir else Path(".data/docs_ingest") / base_slug

        queue: list[str] = [url]
        visited: set[str] = set()
        all_chunks: list[DocChunk] = []

        with httpx2.Client(timeout=30.0) as client:
            while queue and len(visited) < max(1, max_pages):
                current_url = queue.pop(0)
                clean_url = urldefrag(current_url).url
                if clean_url in visited:
                    continue
                visited.add(clean_url)

                try:
                    validate_service_url(clean_url, "Docs Ingestion", allow=False)
                    resp = client.get(clean_url)
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    raw_text = resp.text
                except Exception as exc:
                    masked_url = mask_uri_credentials(clean_url)
                    if len(visited) == 1:
                        raise DocsIngestionError(
                            f"Failed to fetch remote documentation from {masked_url}: {exc}"
                        ) from exc
                    continue

                links: list[str] = []
                if "html" in content_type:
                    parser = _HTMLContentExtractor()
                    parser.feed(raw_text)
                    _, markdown_text, links = parser.get_markdown()
                else:
                    markdown_text = raw_text

                page_slug = (
                    urlparse(clean_url).path.strip("/").replace("/", "_") or base_slug
                ) or "page"
                chunks = _chunk_markdown_content(
                    markdown_text, source=mask_uri_credentials(clean_url), slug=page_slug
                )
                all_chunks.extend(chunks)

                if max_pages > 1 and len(visited) < max_pages:
                    _collect_child_links(links, clean_url, origin_netloc, visited, queue)

        chunk_files = _save_chunks(all_chunks, target_dir)

        return IngestDocResult(
            source=mask_uri_credentials(url),
            is_remote=True,
            total_pages=len(visited),
            total_chunks=len(all_chunks),
            output_dir=str(target_dir),
            chunk_files=chunk_files,
        )


def _collect_child_links(
    links: list[str],
    current_url: str,
    origin_netloc: str,
    visited: set[str],
    queue: list[str],
) -> None:
    """Filter and enqueue candidate links on the same origin domain."""
    for link in links:
        resolved = urljoin(current_url, link)
        p_res = urlparse(resolved)
        is_same_origin = p_res.netloc == origin_netloc and p_res.scheme in ("http", "https")
        if not is_same_origin:
            continue
        if p_res.path.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".tar", ".gz", ".pdf")
        ):
            continue
        clean_res = urldefrag(resolved).url
        if clean_res not in visited and clean_res not in queue:
            queue.append(clean_res)
