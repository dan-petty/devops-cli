"""Unit tests for polyglot source code and technical documentation semantic chunking."""

from __future__ import annotations

from pathlib import Path

import pytest

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
    assert all(c.language in ("terraform", "hcl") for c in chunks)
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

    chunker = SemanticChunker(chunk_size=4)
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

OpenTelemetry Collector routes spans to Tempo.
""",
        encoding="utf-8",
    )

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(doc_file, project_name="org-docs")

    assert len(chunks) >= 3
    assert all(c.category == "docs" for c in chunks)
    assert all(c.project_name == "org-docs" for c in chunks)

    sharding_chunk = next(c for c in chunks if "Sharding & Replicas" in c.symbol_names)
    assert sharding_chunk.section_path == [
        "System Architecture",
        "Vector Storage",
        "Sharding & Replicas",
    ]


@pytest.mark.parametrize(
    ("lang", "extension", "source", "expected_symbols", "forbidden_symbols"),
    [
        (
            "rust",
            "rs",
            """pub struct DatabasePool {
    url: String,
}

impl DatabasePool {
    pub fn new(url: &str) -> Self {
        Self { url: url.to_string() }
    }
}

/*
fn fake_in_comment() {}
*/
""",
            ["new"],
            ["fake_in_comment"],
        ),
        (
            "typescript",
            "ts",
            """export class UserService {
    getUser(
        id: string,
        tenant: string,
    ): string {
        return id + tenant;
    }
}

// function fake_in_comment() {}
""",
            ["getUser"],
            ["fake_in_comment"],
        ),
        (
            "go",
            "go",
            """package main

type Server struct{}

func (s *Server) Start(
    port int,
) error {
    return nil
}

/*
func FakeInComment() {}
*/
""",
            ["Start"],
            ["FakeInComment"],
        ),
        (
            "java",
            "java",
            """public class Service {
    public void processData(
        String input,
        int count
    ) {
    }
}
/*
void fakeInComment() {}
*/
""",
            ["processData"],
            ["fakeInComment"],
        ),
        (
            "csharp",
            "cs",
            """public class Handler {
    public int Calculate(
        int a,
        int b
    ) {
        return a + b;
    }
}
// void FakeInComment() {}
""",
            ["Calculate"],
            ["FakeInComment"],
        ),
        (
            "cpp",
            "cpp",
            """class Processor {
public:
    void Execute(
        int steps
    ) {
    }
};
/*
void FakeInComment() {}
*/
""",
            ["Execute"],
            ["FakeInComment"],
        ),
        (
            "hcl",
            "tf",
            """resource "aws_s3_bucket" "data_lake" {
  bucket = "my-bucket"
}
/*
resource "aws_fake" "comment" {}
*/
""",
            ["data_lake"],
            ["fake"],
        ),
    ],
)
def test_polyglot_tree_sitter_chunking_table(
    tmp_path: Path,
    lang: str,
    extension: str,
    source: str,
    expected_symbols: list[str],
    forbidden_symbols: list[str],
) -> None:
    """Table test: indented definitions and multi-line signatures are captured while comment symbols are ignored."""
    test_file = tmp_path / f"sample.{extension}"
    test_file.write_text(source, encoding="utf-8")

    chunker = SemanticChunker()
    chunks = chunker.chunk_file(test_file, relative_to=tmp_path)

    all_symbols = [s for c in chunks for s in c.symbol_names]
    for exp in expected_symbols:
        assert any(exp in s for s in all_symbols), (
            f"Expected symbol '{exp}' not found in {all_symbols} for {lang}"
        )
    for forb in forbidden_symbols:
        assert not any(forb in s for s in all_symbols), (
            f"Forbidden symbol '{forb}' unexpectedly found in {all_symbols} for {lang}"
        )


@pytest.mark.parametrize("extension", ["py", "rs", "ts", "go", "yaml", "md", "txt"])
def test_chunker_hypothesis_properties(tmp_path: Path, extension: str) -> None:
    """Hypothesis property test feeds generated input to chunker and checks it never raises and line ranges stay inside the file."""
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @settings(max_examples=15, deadline=800)
    @given(payload=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=2000))
    def _run_prop(payload: str) -> None:
        file_path = tmp_path / f"test_{extension}.{extension}"
        file_path.write_text(payload, encoding="utf-8")
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(file_path, relative_to=tmp_path)
        total_lines = max(1, len(payload.splitlines()))
        for c in chunks:
            assert 1 <= c.start_line <= c.end_line <= total_lines

    _run_prop()
