"""AST support for C#, C, C++, shell and Markdown (#506).

These files yielded no symbols, so repomaps, context packing and review grounding saw nothing in
them. The snippets follow the pinned sample repositories: serilog (C#), cJSON (C), fmt (C++), nvm
(shell) and the kind docs (Markdown).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.ast.engine import TreeSitterEngine, detect_language
from devops_cli.ai.ast.fallback import FallbackASTParser

CSHARP = """\
using System;

namespace Serilog
{
    public sealed class LoggerConfiguration
    {
        public LoggerConfiguration() { }

        public Logger CreateLogger() => new Logger();
    }

    public interface ILogEventSink { void Emit(LogEvent logEvent); }
    public readonly struct Token { }
    public record Property(string Name);
    public enum LogEventLevel { Verbose, Debug }
}
"""

CSHARP_FILE_SCOPED = "namespace Serilog.Core;\n\npublic class Logger { void Write() { } }\n"

C_HEADER = """\
#ifndef cJSON__h
#define cJSON__h

#ifdef __cplusplus
extern "C"
{
#endif

#define CJSON_PUBLIC(type) type

typedef struct cJSON
{
    struct cJSON *next;
    int type;
} cJSON;

typedef struct { void *(*allocate)(size_t sz); } cJSON_Hooks;

CJSON_PUBLIC(cJSON *) cJSON_Parse(const char *value);
CJSON_PUBLIC(const char*) cJSON_Version(void);
struct opaque;

#ifdef __cplusplus
}
#endif

#endif
"""

C_SOURCE = """\
static unsigned char *print_number(const cJSON *item)
{
    return NULL;
}

CJSON_PUBLIC(void) cJSON_Delete(cJSON *item)
{
    int local(void);
}

enum parse_state { START, DONE };
"""

CPP_HEADER = """\
#include <string>

namespace fmt {
template <typename T> class basic_appender {
 public:
  basic_appender(T* out) : out_(out) {}
  ~basic_appender() {}
  auto operator++() -> basic_appender& { return *this; }
  void push_back(T c);

 private:
  T* out_;
};

struct format_specs { int width; };
enum class align { left, right };
using string_view = std::string;

template <typename T> auto to_string(const T& value) -> std::string { return {}; }
}  // namespace fmt

void fmt::basic_appender<char>::push_back(char c) {}
"""

SHELL = """\
#!/usr/bin/env bash
nvm_echo() {
  command printf %s\\\\n "$*" 2>/dev/null
}

function nvm_cd {
  \\cd "$@"
}
"""

MARKDOWN = """\
---
title: "Quick Start"
---

# Installation

Install kind.

Installing From Source
----------------------

```bash
# not a heading
make build
```

## Creating a Cluster ##
"""


def _symbols(code: str, language: str) -> list[tuple[str, str, str | None]]:
    parsed = TreeSitterEngine().parse_code(code, language)
    assert parsed.parse_engine == "tree-sitter"
    return [(s.kind.value, s.name, s.parent_scope) for s in parsed.symbols]


def test_csharp_namespaces_types_and_members() -> None:
    """Verify namespaces, each kind of type, and methods and constructors in their class."""
    assert (_symbols(CSHARP, "csharp"), _symbols(CSHARP_FILE_SCOPED, "csharp")) == (
        [
            ("module", "Serilog", None),
            ("class", "LoggerConfiguration", None),
            ("method", "LoggerConfiguration", "LoggerConfiguration"),
            ("method", "CreateLogger", "LoggerConfiguration"),
            ("interface", "ILogEventSink", None),
            ("method", "Emit", "ILogEventSink"),
            ("struct", "Token", None),
            ("class", "Property", None),
            ("type", "LogEventLevel", None),
        ],
        [
            ("module", "Serilog.Core", None),
            ("class", "Logger", None),
            ("method", "Write", "Logger"),
        ],
    )


def test_c_headers_declare_their_api_through_guards_linkage_and_export_macros() -> None:
    """Verify prototypes inside an include guard and `extern "C"`, behind an export macro, are
    named by the function; a struct is a symbol only where it is defined."""
    assert _symbols(C_HEADER, "c") == [
        ("function", "CJSON_PUBLIC", None),
        ("type", "cJSON", None),
        ("struct", "cJSON", None),
        ("type", "cJSON_Hooks", None),
        ("function", "cJSON_Parse", None),
        ("function", "cJSON_Version", None),
    ]


def test_c_definitions_are_named_through_their_declarators() -> None:
    """Verify pointer-returning and macro-wrapped definitions are named, and a declaration
    inside a function body is not an API."""
    assert _symbols(C_SOURCE, "c") == [
        ("function", "print_number", None),
        ("function", "cJSON_Delete", None),
        ("type", "parse_state", None),
    ]


def test_cpp_namespaces_classes_members_and_out_of_class_definitions() -> None:
    """Verify in-class members are methods of their class, an out-of-class definition is a
    method by its qualified name, and templates, aliases and scoped enums are found."""
    assert _symbols(CPP_HEADER, "cpp") == [
        ("module", "fmt", None),
        ("class", "basic_appender", None),
        ("method", "basic_appender", "basic_appender"),
        ("method", "~basic_appender", "basic_appender"),
        ("method", "operator++", "basic_appender"),
        ("struct", "format_specs", None),
        ("type", "align", None),
        ("type", "string_view", None),
        ("function", "to_string", None),
        ("method", "fmt::basic_appender<char>::push_back", None),
    ]


def test_shell_functions_in_both_forms() -> None:
    """Verify `name() {}` and `function name {}` are both functions."""
    assert _symbols(SHELL, "bash") == [
        ("function", "nvm_echo", None),
        ("function", "nvm_cd", None),
    ]


def test_markdown_headings_skip_front_matter_and_code() -> None:
    """Verify ATX and setext headings are found, closing hashes dropped, and neither front
    matter nor a `#` comment in a fenced block is a heading."""
    assert _symbols(MARKDOWN, "markdown") == [
        ("heading", "Installation", None),
        ("heading", "Installing From Source", None),
        ("heading", "Creating a Cluster", None),
    ]


@pytest.mark.parametrize(
    ("name", "language"),
    [
        ("Logger.cs", "csharp"),
        ("cJSON.c", "c"),
        ("format.cc", "cpp"),
        ("format.cpp", "cpp"),
        ("core.hpp", "cpp"),
        ("nvm.sh", "bash"),
        ("install.bash", "bash"),
        ("15-local-resolvers.envsh", "bash"),
        ("README.md", "markdown"),
        ("cJSON.h", "c"),
    ],
)
def test_extensions_name_their_language(name: str, language: str) -> None:
    """Verify each new extension is recognised; a header starts out as C."""
    assert detect_language(name) == language


def test_a_header_is_parsed_as_the_language_it_is_written_in(tmp_path: Path) -> None:
    """Verify a C++ header, as fmt's are, is parsed as C++, and a C header as C."""
    (tmp_path / "cJSON.h").write_text(C_HEADER, encoding="utf-8")
    (tmp_path / "format.h").write_text(CPP_HEADER, encoding="utf-8")
    engine = TreeSitterEngine()

    c_header = engine.parse_file(tmp_path / "cJSON.h")
    cpp_header = engine.parse_file(tmp_path / "format.h")

    assert (
        c_header.language if c_header else None,
        cpp_header.language if cpp_header else None,
        "basic_appender" in {s.name for s in (cpp_header.symbols if cpp_header else [])},
    ) == ("c", "cpp", True)


@pytest.mark.parametrize(
    ("code", "language", "expected"),
    [
        (
            CSHARP,
            "csharp",
            [
                ("module", "Serilog"),
                ("class", "LoggerConfiguration"),
                ("method", "LoggerConfiguration"),
                ("method", "CreateLogger"),
                ("interface", "ILogEventSink"),
                ("struct", "Token"),
                ("class", "Property"),
                ("type", "LogEventLevel"),
            ],
        ),
        (
            C_SOURCE,
            "c",
            [("function", "print_number"), ("function", "cJSON_Delete"), ("type", "parse_state")],
        ),
        (
            "namespace fmt {\nclass writer {\n};\nint format(const char* s)\n{\n  if (s) return 1;\n}\n"
            "int answer() { return 42; }\n}\n",
            "cpp",
            [
                ("module", "fmt"),
                ("class", "writer"),
                ("function", "format"),
                ("function", "answer"),
            ],
        ),
        (SHELL, "bash", [("function", "nvm_echo"), ("function", "nvm_cd")]),
        (
            MARKDOWN,
            "markdown",
            [("heading", "Installation"), ("heading", "Creating a Cluster")],
        ),
    ],
)
def test_the_fallback_finds_functions_types_and_headings(
    code: str, language: str, expected: list[tuple[str, str]]
) -> None:
    """Verify the regex fallback, used without a grammar, finds declarations and ATX headings,
    and skips control statements, calls, front matter and fenced code."""
    parsed = FallbackASTParser().parse("snippet", code, language)

    assert [(s.kind.value, s.name) for s in parsed.symbols] == expected


@pytest.mark.parametrize(
    ("alias", "language"),
    [("shell", "bash"), ("sh", "bash"), ("C#", "csharp"), ("c++", "cpp"), ("md", "markdown")],
)
def test_languages_are_found_by_their_other_names(alias: str, language: str) -> None:
    """Verify the names the analysis scanner and users give a language reach its grammar."""
    engine = TreeSitterEngine()

    assert (engine.is_language_supported(alias), engine.parse_code("", alias).language) == (
        True,
        language,
    )
