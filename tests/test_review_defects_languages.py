"""Synthetic defect templates for application languages (#503).

TypeScript/JavaScript, Go, Rust, Java, C# and C/C++ get the defects the Python templates
inject: dropped guards and error checks, dropped awaits, disabled TLS verification and widened
file modes, and for C/C++ unbounded string calls. A guard is removed only as a complete,
balanced statement, so the mutated file stays well formed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.review.defects import generate_corpus, select_templates


def _mutate(
    template: str, filename: str, text: str
) -> tuple[str, tuple[int, int], tuple[str, ...]]:
    """The file after the template's first site is applied, and where a report of it counts."""
    (chosen,) = select_templates([template])
    find = chosen.finder_for(filename)
    assert find is not None
    lines = text.splitlines(keepends=True)
    site = find(lines)[0]
    return (
        "".join([*lines[: site.start], *site.replacement, *lines[site.end :]]),
        site.region,
        site.evidence,
    )


def _sites(template: str, filename: str, text: str) -> int:
    (chosen,) = select_templates([template])
    find = chosen.finder_for(filename)
    assert find is not None
    return len(find(text.splitlines(keepends=True)))


TS_TAKE = """export function take(items: string[], n: number): string[] {
\tif (n > items.length) {
\t\tthrow new RangeError('too many');
\t}
\treturn items.slice(0, n);
}
"""
GO_LOAD = """func load(path string) ([]byte, error) {
\tdata, err := os.ReadFile(path)
\tif err != nil {
\t\treturn nil, err
\t}
\treturn data, err
}
"""
RUST_TAKE = """fn take(items: &[u8], limit: usize) -> Result<&[u8], Error> {
    if limit > items.len() {
        return Err(Error::TooMany);
    }
    Ok(&items[..limit])
}
"""
JAVA_LOAD = """  public Config load(String name) {
    if (name == null) {
      throw new IllegalArgumentException("name");
    }
    return read(name);
  }
"""
CSHARP_WRITE = """    public void Write(string message)
    {
        if (message == null)
        {
            throw new ArgumentNullException(nameof(message));
        }
        _sink.Emit(message);
    }
"""
C_COPY = """int copy(char *dest, size_t size, const char *source, size_t length) {
    if (length >= size) return -1;
    memcpy(dest, source, length);
    return 0;
}
"""


@pytest.mark.parametrize(
    ("template", "filename", "text", "expected", "region", "evidence"),
    [
        (
            "drop-bounds-check",
            "take.ts",
            TS_TAKE,
            "export function take(items: string[], n: number): string[] {\n"
            "\treturn items.slice(0, n);\n}\n",
            (1, 12),
            # `items` and `length` are too generic to tie a finding to this code.
            (),
        ),
        (
            "drop-error-check",
            "load.go",
            GO_LOAD,
            "func load(path string) ([]byte, error) {\n\tdata, err := os.ReadFile(path)\n"
            "\treturn data, err\n}\n",
            (1, 13),
            (),
        ),
        (
            "drop-bounds-check",
            "take.rs",
            RUST_TAKE,
            "fn take(items: &[u8], limit: usize) -> Result<&[u8], Error> {\n"
            "    Ok(&items[..limit])\n}\n",
            (1, 12),
            ("limit",),
        ),
        (
            "drop-error-check",
            "Loader.java",
            JAVA_LOAD,
            "  public Config load(String name) {\n    return read(name);\n  }\n",
            (1, 12),
            (),
        ),
        (
            "drop-error-check",
            "Logger.cs",
            CSHARP_WRITE,
            "    public void Write(string message)\n    {\n        _sink.Emit(message);\n    }\n",
            (2, 13),
            (),
        ),
        (
            "drop-bounds-check",
            "copy.c",
            C_COPY,
            "int copy(char *dest, size_t size, const char *source, size_t length) {\n"
            "    memcpy(dest, source, length);\n    return 0;\n}\n",
            (1, 12),
            (),
        ),
    ],
)
def test_a_guard_is_removed_as_a_whole_statement(
    template: str,
    filename: str,
    text: str,
    expected: str,
    region: tuple[int, int],
    evidence: tuple[str, ...],
) -> None:
    """Verify each language's guard goes whole, braces and all, and where a report counts."""
    assert _mutate(template, filename, text) == (expected, region, evidence)


@pytest.mark.parametrize(
    ("template", "filename", "text"),
    [
        # The body does more than exit.
        ("drop-bounds-check", "a.ts", "if (a > b) {\n  log(a);\n  return;\n}\n"),
        # An else branch would be left dangling.
        ("drop-bounds-check", "a.java", "if (a > b) {\n  return 1;\n} else {\n  return 2;\n}\n"),
        # Not a statement of its own.
        ("drop-bounds-check", "a.c", "} else if (a > b) return -1;\n"),
        # The body of a braceless loop: removing it would take the next statement instead.
        ("drop-bounds-check", "a.c", "for (i = 0; i < n; i++)\n    if (a[i] > max) return -1;\n"),
        # Inside a string.
        ("drop-bounds-check", "a.js", 'const s = "if (a > b) { return }";\n'),
        # Go would not compile: err is never read again.
        (
            "drop-error-check",
            "a.go",
            GO_LOAD.replace("\treturn data, err\n", "\treturn data, nil\n"),
        ),
        # An init statement would take the call with the check.
        ("drop-error-check", "a.go", "\tif err := run(); err != nil {\n\t\treturn err\n\t}\n"),
        # A guard continued over lines without braces.
        ("drop-bounds-check", "a.cs", "if (a > b)\n    return;\n"),
        ("drop-await", "a.js", "for await (const chunk of stream) {}\n"),
        ("drop-await", "a.cs", "await foreach (var item in items) {}\n"),
        ("unbounded-string-copy", "a.c", "strncpy(dest,\n        source, size);\n"),
        ("disable-tls-verify", "a.ts", "const agent = { rejectUnauthorized: false };\n"),
    ],
)
def test_places_that_would_break_or_have_no_defect_are_skipped(
    template: str, filename: str, text: str
) -> None:
    """Verify no site where the mutation would not be well formed or changes nothing."""
    assert _sites(template, filename, text) == 0


@pytest.mark.parametrize(
    ("template", "filename", "line", "expected"),
    [
        (
            "drop-await",
            "user.ts",
            "  const user = await this.fetchUser(id);\n",
            "  const user = this.fetchUser(id);\n",
        ),
        (
            "drop-await",
            "Client.cs",
            "        var body = await client.GetStringAsync(url);\n",
            "        var body = client.GetStringAsync(url);\n",
        ),
        (
            "unbounded-string-copy",
            "copy.c",
            "    strncpy(dest, source, sizeof(dest) - 1);\n",
            "    strcpy(dest, source);\n",
        ),
        (
            "unbounded-string-copy",
            "fmt.cpp",
            '    snprintf(buffer, sizeof buffer, "%s:%d", host, port);\n',
            '    sprintf(buffer, "%s:%d", host, port);\n',
        ),
        (
            "disable-tls-verify",
            "agent.ts",
            "const agent = new https.Agent({ keepAlive: true });\n",
            "const agent = new https.Agent({ rejectUnauthorized: false, keepAlive: true });\n",
        ),
        (
            "disable-tls-verify",
            "client.js",
            "  rejectUnauthorized: true,\n",
            "  rejectUnauthorized: false,\n",
        ),
        (
            "disable-tls-verify",
            "client.go",
            "\tcfg := &tls.Config{MinVersion: tls.VersionTLS12}\n",
            "\tcfg := &tls.Config{InsecureSkipVerify: true, MinVersion: tls.VersionTLS12}\n",
        ),
        (
            "disable-tls-verify",
            "client.rs",
            "    let client = Client::builder().build()?;\n",
            "    let client = Client::builder().danger_accept_invalid_certs(true).build()?;\n",
        ),
        (
            "disable-tls-verify",
            "Client.cs",
            "        var handler = new HttpClientHandler();\n",
            "        var handler = new HttpClientHandler { ServerCertificateCustomValidationCallback"
            " = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator };\n",
        ),
        ("widen-file-mode", "dir.go", "\tos.MkdirAll(dir, 0o700)\n", "\tos.MkdirAll(dir, 0o777)\n"),
        (
            "widen-file-mode",
            "key.go",
            "\tos.WriteFile(path, data, 0600)\n",
            "\tos.WriteFile(path, data, 0666)\n",
        ),
        (
            "widen-file-mode",
            "key.ts",
            "fs.writeFileSync(file, data, { mode: 0o600 });\n",
            "fs.writeFileSync(file, data, { mode: 0o666 });\n",
        ),
        (
            "widen-file-mode",
            "key.rs",
            "    options.mode(0o600);\n",
            "    options.mode(0o666);\n",
        ),
        ("widen-file-mode", "dir.c", "    mkdir(path, 0700);\n", "    mkdir(path, 0777);\n"),
        (
            "widen-file-mode",
            "Keys.java",
            '    Files.createFile(p, asFileAttribute(PosixFilePermissions.fromString("rw-------")));\n',
            '    Files.createFile(p, asFileAttribute(PosixFilePermissions.fromString("rw-rw-rw-")));\n',
        ),
    ],
)
def test_a_line_defect_is_injected_in_each_language(
    template: str, filename: str, line: str, expected: str
) -> None:
    """Verify the one-line defects, each at the line it changes."""
    assert _mutate(template, filename, line)[:2] == (expected, (1, 1))


def test_a_corpus_of_mixed_languages_records_each_injection(tmp_path: Path) -> None:
    """Verify corpus generation injects into each language and records the template used."""
    sources = {
        "take.ts": TS_TAKE,
        "load.go": GO_LOAD,
        "take.rs": RUST_TAKE,
        "Loader.java": JAVA_LOAD,
        "Logger.cs": CSHARP_WRITE,
        "copy.c": C_COPY,
    }
    for name, text in sources.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    corpus = generate_corpus(
        [(tmp_path / name, name) for name in sources],
        tmp_path / "corpus",
        sources=[str(tmp_path)],
        seed=1,
        templates=select_templates(["drop-bounds-check", "drop-error-check"]),
    )

    assert sorted((i.file, i.template) for i in corpus.injections) == [
        ("Loader.java", "drop-error-check"),
        ("Logger.cs", "drop-error-check"),
        ("copy.c", "drop-bounds-check"),
        ("load.go", "drop-error-check"),
        ("take.rs", "drop-bounds-check"),
        ("take.ts", "drop-bounds-check"),
    ]
