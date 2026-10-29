# Proposal

## Why

Issue #2010, part 1 of #1876. Ruff `PLR1702` is a preview rule. With preview on, Ruff also reports findings of other rules that the code had. Until that code is rewritten, #1876 cannot turn on preview and replace the nesting hook with Ruff.

## What Changes

- The lazy-export modules `ai/review`, `ai/rag`, `ai/models`, `ai/benchmark` and `tests/support/fakes` import their exported names under `if TYPE_CHECKING:`. Each block is made from the module's own export map, so it names the same source module and attribute that `__getattr__` loads. At run time nothing more is imported: the modules stay lazy.
- `AbstractToolset` and `FunctionToolset` (`ai/toolsets`) use PEP 695 type parameters, `[DepsT = Any]`, in place of `Generic[DepsT]`. The module-level `TypeVar` that only they used is deleted.
- `format_duration` and its test write the micro sign as the escape `\u00b5`. The output text does not change: `format_duration(0.0005)` returns `500µs`.
- `tests/test_fast_dispatch.py` loses `import devops_cli.core`, which nothing in the file uses.
- No Ruff, mypy or ceiling setting changes.
- The change keeps every behavior a consumer observes, so it has no spec delta (`skip_specs: true`).
- This change fits one pull request.

## Impact

- `src/devops_cli/ai/{review,rag,models,benchmark,toolsets}/__init__.py`, `src/devops_cli/output/formatters/scalars.py`.
- `tests/support/fakes/__init__.py`, `tests/test_output.py`, `tests/test_fast_dispatch.py`.

## Feasibility

Measured with Ruff 0.16.8, the settings of `pyproject.toml`, `--preview`, `lint.explicit-preview-rules = true` and `PLR1702` at `max-nested-blocks = 5`, the setup that #1876 uses:

| Rule | origin/main 33491ca1 | This change |
| :--- | ---: | ---: |
| `F822` | 82 | 0 |
| `UP046` | 2 | 0 |
| `RUF001` | 2 | 0 |
| `F401` | 1 | 0 |
| `PLR1702` | 0 | 0 |

- The issue named 8 modules. On 33491ca1, `core`, `config` and the package root report no `F822`, so 5 modules remain. The `F401` site moved: `tests/test_exceptions.py` is clean, and the one finding is `tests/test_fast_dispatch.py:10`.
- Importing each of the 5 packages loads none of its submodules, as before. Access by name still loads the attribute.
- `uv run mypy src` passes in strict mode (570 files). `FunctionToolset[int]` still parametrizes, and both classes keep `__type_params__ == (DepsT,)`.
- `ruff check --preview` with every preview-only rule turned on (no `explicit-preview-rules`) reports other preview-only rules. #1876 does not turn those on, so they are out of scope here.

## Existing Tool Considered

Ruff finds each problem, and the fixes use the standard Python forms: `if TYPE_CHECKING:` imports, PEP 695 and PEP 696 type parameters, and a `\u` escape. `lint.per-file-ignores` would turn a rule off for whole files, which the owner refused on #1876. Nothing is built, and no code is deleted beyond the unused `TypeVar` and the unused import.
