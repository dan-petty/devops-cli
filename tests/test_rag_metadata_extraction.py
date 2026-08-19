"""Unit tests for RAG structured metadata extraction and security tagging."""

from __future__ import annotations

from devops_cli.ai.rag.metadata import (
    extract_code_metadata,
    extract_doc_frontmatter,
    extract_doc_metadata,
    extract_imports,
    extract_security_tags,
)


def test_extract_security_tags() -> None:
    code = """
import keyring
from cryptography.hazmat.primitives.ciphers import Cipher
import httpx2
import asyncpg

def authenticate_user(token: str):
    pass
"""
    tags = extract_security_tags(code)
    assert "crypto" in tags
    assert "network" in tags
    assert "auth" in tags
    assert "secrets" in tags
    assert "db" in tags


def test_extract_imports_python() -> None:
    code = """
import os
import sys
from pathlib import Path
from devops_cli.config.settings import load_settings
"""
    imports = extract_imports(code, language="python")
    assert "os" in imports
    assert "sys" in imports
    assert "pathlib" in imports
    assert "devops_cli.config.settings" in imports


def test_extract_imports_polyglot() -> None:
    go_code = """
package main
import (
    "fmt"
    "net/http"
)
"""
    go_imports = extract_imports(go_code, language="go")
    assert "fmt" in go_imports
    assert "net/http" in go_imports

    ts_code = """
import React, { useState } from 'react';
import { Button } from '@shadcn/ui';
const axios = require('axios');
"""
    ts_imports = extract_imports(ts_code, language="typescript")
    assert "react" in ts_imports
    assert "@shadcn/ui" in ts_imports
    assert "axios" in ts_imports


def test_extract_doc_frontmatter() -> None:
    doc = """---
title: System Architecture Guide
author: DevOps Team
category: architecture
tags: k8s, qdrant, otel
---

# Architecture Overview

Content here...
"""
    fm = extract_doc_frontmatter(doc)
    assert fm.get("title") == "System Architecture Guide"
    assert fm.get("author") == "DevOps Team"
    assert fm.get("category") == "architecture"

    meta = extract_doc_metadata(doc, section_path=["Architecture", "Overview"])
    assert meta["depth"] == 2
    assert meta["root_section"] == "Architecture"
    assert meta["frontmatter"]["title"] == "System Architecture Guide"


def test_extract_code_metadata() -> None:
    code = """
import httpx2

def fetch_data(url: str) -> str:
    res = httpx2.get(url)
    return res.text
"""
    meta = extract_code_metadata(code, language="python", symbols=["fetch_data"])
    assert meta["line_count"] >= 5
    assert meta["symbols_count"] == 1
    assert "httpx2" in meta["imports"]
    assert "network" in meta["security_tags"]
