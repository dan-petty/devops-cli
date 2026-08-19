"""Unit tests for polyglot source code and technical documentation semantic chunking."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.rag.chunker import SemanticChunker


def test_chunk_go(tmp_path: Path) -> None:
    go_file = tmp_path / "main.go"
    go_file.write_text(
        """package main

import "fmt"

type ServerConfig struct {
    Port int
    Host string
}

func StartServer(cfg ServerConfig) error {
    fmt.Println("Server running")
    return nil
}
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(go_file, project_name="my-go-app")

    assert len(chunks) >= 2
    languages = {c.language for c in chunks}
    assert "go" in languages
    symbols = [s for c in chunks for s in c.symbol_names]
    assert any("ServerConfig" in s for s in symbols)
    assert any("StartServer" in s for s in symbols)
    assert all(c.project_name == "my-go-app" for c in chunks)


def test_chunk_rust(tmp_path: Path) -> None:
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text(
        """pub struct DatabasePool {
    url: String,
}

impl DatabasePool {
    pub fn new(url: &str) -> Self {
        Self { url: url.to_string() }
    }
}

pub async fn execute_query(pool: &DatabasePool) -> Result<(), ()> {
    Ok(())
}
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(rs_file, project_name="rust-core")

    assert len(chunks) >= 2
    assert all(c.language == "rust" for c in chunks)
    symbols = [s for c in chunks for s in c.symbol_names]
    assert any("DatabasePool" in s for s in symbols)
    assert any("execute_query" in s for s in symbols)


def test_chunk_typescript(tmp_path: Path) -> None:
    ts_file = tmp_path / "app.tsx"
    ts_file.write_text(
        """export interface UserProfile {
    id: string;
    name: string;
}

export class UserService {
    getUser(id: string): UserProfile {
        return { id, name: "Alice" };
    }
}

export const AppHeader = () => {
    return <header>App Header</header>;
};
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(ts_file, project_name="web-frontend")

    assert len(chunks) >= 2
    assert all(c.language == "typescript" for c in chunks)
    symbols = [s for c in chunks for s in c.symbol_names]
    assert any("UserProfile" in s for s in symbols)
    assert any("UserService" in s for s in symbols)


def test_chunk_terraform(tmp_path: Path) -> None:
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        """resource "aws_s3_bucket" "data_lake" {
  bucket = "my-org-data-lake"
  acl    = "private"
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "3.0.0"
}
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(tf_file, project_name="cloud-infra")

    assert len(chunks) >= 2
    assert all(c.language == "terraform" for c in chunks)
    assert all(c.category == "iac" for c in chunks)


def test_chunk_sql(tmp_path: Path) -> None:
    sql_file = tmp_path / "schema.sql"
    sql_file.write_text(
        """CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(sql_file, project_name="db-migrations")

    assert len(chunks) >= 2
    assert all(c.language == "sql" for c in chunks)


def test_chunk_technical_docs_with_breadcrumbs(tmp_path: Path) -> None:
    doc_file = tmp_path / "ARCHITECTURE.md"
    doc_file.write_text(
        """# System Architecture

High level overview of our systems.

## Vector Storage

We use Qdrant for storing vector embeddings.

### Sharding & Replicas

Details on vector collection sharding and replica distribution.

## Observability & Tracing

OpenTelemetry Collector routes spans to Jaeger.
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(doc_file, project_name="org-docs")

    assert len(chunks) >= 3
    assert all(c.category == "docs" for c in chunks)
    assert all(c.project_name == "org-docs" for c in chunks)

    # Verify hierarchical breadcrumbs
    sharding_chunk = [c for c in chunks if "Sharding & Replicas" in c.symbol_names][0]
    assert sharding_chunk.section_path == [
        "System Architecture",
        "Vector Storage",
        "Sharding & Replicas",
    ]
