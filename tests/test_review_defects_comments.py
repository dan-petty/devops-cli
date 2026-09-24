"""Synthetic defects are never injected into comments (#537).

The brace-language finders blanked string literals and one-line comments, but not a block comment
spanning lines. So code examples in JSDoc counted as code: 9 of the 78 injections of the first
sample validation (#505) were in comments, all dropped awaits in ky's documentation.
"""

from __future__ import annotations

import pytest

from devops_cli.ai.review.defects import select_templates


def _sites(template: str, filename: str, text: str) -> list[int]:
    """The 1-based lines a template would change."""
    (chosen,) = select_templates([template])
    find = chosen.finder_for(filename)
    assert find is not None
    return [site.start + 1 for site in find(text.splitlines(keepends=True))]


JSDOC_EXAMPLE = """/**
Fetch JSON.

@example
```
const json = await ky('https://example.com').json();
```
*/
export async function get(url: string) {
\treturn await ky(url).json();
}
"""


@pytest.mark.parametrize(
    ("template", "filename", "text", "lines"),
    [
        # An example in JSDoc is not code; the await after it is.
        ("drop-await", "get.ts", JSDOC_EXAMPLE, [10]),
        # A guard inside a comment; the same guard in code.
        (
            "drop-bounds-check",
            "copy.c",
            "/*\n    if (len > max) return -1;\n*/\nint f(int len, int max) {\n"
            "    if (len > max) return -1;\n    return 0;\n}\n",
            [5],
        ),
        # Code after a comment closes on the same line.
        ("drop-await", "load.ts", "/* started\n   here */ await load();\n", [2]),
        # A `/*` inside a string opens no comment, and `//` in a URL none either.
        ("drop-await", "glob.ts", 'const glob = "src/**/*.ts";\nawait load(glob);\n', [2]),
        ("drop-await", "url.js", 'const r = await fetch("https://example.com/a");\n', [1]),
        # One-line comments.
        ("disable-tls-verify", "agent.ts", "// rejectUnauthorized: true\n", []),
        (
            "widen-file-mode",
            "dir.go",
            "// os.MkdirAll(dir, 0o700)\nos.MkdirAll(dir, 0o700) // private\n",
            [2],
        ),
        # Block comments spanning lines, in each language with substitutions.
        (
            "disable-tls-verify",
            "client.go",
            "/*\n\tInsecureSkipVerify: false,\n*/\ncfg := &tls.Config{InsecureSkipVerify: false}\n",
            [4],
        ),
        (
            "disable-tls-verify",
            "client.rs",
            "/*\n    danger_accept_invalid_certs(false)\n*/\n",
            [],
        ),
        (
            "disable-tls-verify",
            "Client.cs",
            "/*\n  var handler = new HttpClientHandler();\n*/\nvar h = new HttpClientHandler();\n",
            [4],
        ),
        (
            "widen-file-mode",
            "Keys.java",
            '/**\n * PosixFilePermissions.fromString("rw-------")\n */\n',
            [],
        ),
        (
            "unbounded-string-copy",
            "copy.c",
            "/*\n    strncpy(dest, source, n);\n*/\n    strncpy(dest, source, n);\n",
            [4],
        ),
        (
            "disable-encryption",
            "db.tf",
            "/*\n  storage_encrypted = true\n*/\n  storage_encrypted = true\n",
            [4],
        ),
    ],
)
def test_defects_go_into_code_never_into_comments(
    template: str, filename: str, text: str, lines: list[int]
) -> None:
    """Verify only the lines holding code are sites."""
    assert _sites(template, filename, text) == lines
