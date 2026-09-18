"""Unit tests for semantic chunker (AST, YAML, Markdown, sliding window)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.rag.chunker import SemanticChunker


def test_chunk_python_file(tmp_path: Path) -> None:
    code = '''"""Sample module."""

class MyService:
    def execute(self) -> None:
        pass

def top_level_func(a: int) -> int:
    return a + 1
'''
    py_file = tmp_path / "service.py"
    py_file.write_text(code, encoding="utf-8")

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(py_file, relative_to=tmp_path)

    assert len(chunks) >= 2
    symbols = [sym for c in chunks for sym in c.symbol_names]
    assert "MyService" in symbols or "MyService.execute" in symbols
    assert "top_level_func" in symbols
    assert all(c.language == "python" for c in chunks)


def test_chunk_yaml_manifests(tmp_path: Path) -> None:
    manifest = """apiVersion: v1
kind: Service
metadata:
  name: my-svc
spec:
  ports:
    - port: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-deploy
spec:
  replicas: 1
"""
    yaml_file = tmp_path / "k8s.yaml"
    yaml_file.write_text(manifest, encoding="utf-8")

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(yaml_file, relative_to=tmp_path)

    assert len(chunks) == 2
    assert chunks[0].doc_type == "manifest"
    assert "Service" in chunks[0].symbol_names or "my-svc" in chunks[0].symbol_names
    assert "Deployment" in chunks[1].symbol_names or "my-deploy" in chunks[1].symbol_names


def test_chunk_markdown(tmp_path: Path) -> None:
    doc = """# Introduction
This is the intro section.

## Architecture
Architecture details here.

## Deployment
Deployment instructions.
"""
    md_file = tmp_path / "README.md"
    md_file.write_text(doc, encoding="utf-8")

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(md_file, relative_to=tmp_path)

    assert len(chunks) >= 2
    assert all(c.doc_type == "doc" for c in chunks)
    titles = [s for c in chunks for s in c.symbol_names]
    assert any("Architecture" in t for t in titles)


def test_chunk_file_defensive_boundaries(tmp_path: Path) -> None:
    """Verify that chunk_file defensively returns empty list for symlinks, oversized files, and traversal attempts."""
    from unittest.mock import MagicMock

    chunker = SemanticChunker()

    # 1. Path outside relative_to (containment check)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "external.py"
    outside_file.write_text("x = 1\n", encoding="utf-8")
    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()
    chunks_traversal = chunker.chunk_file(outside_file, relative_to=inside_dir)

    # 2. Symlink
    target_file = inside_dir / "real.py"
    target_file.write_text("y = 2\n", encoding="utf-8")
    symlink_file = inside_dir / "link.py"
    symlink_file.symlink_to(target_file)
    chunks_symlink = chunker.chunk_file(symlink_file, relative_to=inside_dir)

    # 3. Oversized file (> 5MB)
    mock_large = MagicMock(spec=Path)
    mock_large.resolve.return_value = mock_large
    mock_large.is_symlink.return_value = False
    mock_large.is_file.return_value = True
    mock_large.is_relative_to.return_value = True
    mock_large.stat.return_value.st_size = 6 * 1024 * 1024
    mock_large.relative_to.return_value = Path("huge.py")
    mock_large.suffix = ".py"
    chunks_oversized = chunker.chunk_file(mock_large, relative_to=inside_dir)

    assert (chunks_traversal, chunks_symlink, chunks_oversized) == ([], [], [])
