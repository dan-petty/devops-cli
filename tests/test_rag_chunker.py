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
