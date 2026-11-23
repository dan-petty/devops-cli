# Proposal: #6830

## Why

Two columns of `docs/ERRORS.md` are wrong. The description holds only the first line of the docstring, so 16 rows end in the middle of a sentence. The domain of a class outside `devops_cli.exceptions` is its whole module path, such as `Devops_cli.github.onboard.baseline`, in 22 rows. Closes #6830.

## What Changes

- `DocGenerator.catalog_description` gives the first paragraph of the docstring on one line, with each bar escaped.
- `DocGenerator.catalog_domain` gives the area of the module: the first name below the package, or the module name below `devops_cli.exceptions`.
- `docs/ERRORS.md` is generated again.

## Capabilities

- `docs-error-catalog`: a new requirement for the description and the domain of a row.

## Impact

Only `docs/ERRORS.md` changes. The error codes and exit statuses do not change.

## Feasibility

On origin/main, 16 rows end mid-sentence and 22 rows show a module path as the domain. A scratch count of the generated file confirms both numbers.

## Existing Tool Considered

`inspect.cleandoc` of the standard library cleans the docstring. The library `docstring-parser` gives only the first line as its short description, so it does not fix the wrapped rows. No other tool is needed.
