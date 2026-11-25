# Tasks

## 1. Add the docs dark token config and its build output

Kind: other. Reads: `design/sd/dark.json`, `design/tokens/dark.tokens.json`, `src/devops_cli/design/tokens-dark.css`, `Makefile`, `tests/design/test_tokens.py`. Changes: `design/sd/dark-docs.json` (new), `docs/assets/css/tokens-dark-docs.css` (new), `Makefile`, `tests/config/test_docs_theme.py` (new).

- [ ] 1.1 Add `design/sd/dark-docs.json` in the shape of `design/sd/dark.json`: the source design/tokens/dark.tokens.json, the transform group css, the buildPath docs/assets/css/ and one css/variables file named tokens-dark-docs.css with the selector :root[data-md-color-scheme="slate"] and outputReferences true. Add the build line `$(STYLE_DICTIONARY) build -c design/sd/dark-docs.json` to the `design-tokens` target of `Makefile`, after the dark-explicit line. style-dictionary is NOT_IN_RUNNER, so write `docs/assets/css/tokens-dark-docs.css` as the build writes it, from `src/devops_cli/design/tokens-dark.css`: the same declarations in the same order, under the slate selector. The Design Tokens job runs make design-tokens and fails when the file is not the build. Add the case test_the_docs_dark_file_holds_the_slate_selector_and_the_package_values to `tests/config/test_docs_theme.py`, which reads each declaration of both files with its own regex and compares names and values
  - Verification: `$ uv run devops ci test tests/config/test_docs_theme.py` passes

## 2. Map the Zensical theme variables to the token variables

Kind: other. Reads: `docs/DESIGN.md`, `docs/assets/css/tokens-base.css`, `docs/assets/css/tokens-light.css`, `docs/assets/css/tokens-dark-docs.css`. Changes: `docs/assets/css/site/theme.css` (new), `tests/config/test_docs_theme.py`.

- [ ] 2.1 Add `docs/assets/css/site/theme.css`. Set the Zensical theme variables that `docs/DESIGN.md` gives a token role: the page background, the surface, the body text, the muted text, the link, the accent, the code background, the code text, the primary color and the footer. Each value is a var() of a variable of `docs/assets/css/tokens-base.css`, `docs/assets/css/tokens-light.css` or `docs/assets/css/tokens-dark-docs.css`. Set the code highlight variables to the syntax tokens: the comment in italics, the string, the keyword at weight 600 and the foreground for all other code. Add the focus-visible rule with the focus width and offset tokens, the min-width 40rem and min-width 75rem rules, the doc-caption and doc-caption--table classes, and one Google Fonts css2 import that names Source Serif 4, Source Sans 3 and Source Code Pro with display=swap. Hold no color literal. Add the cases for the token map, the contrast of each pair, the focus rule, the breakpoints, the captions, the code roles and the font request to `tests/config/test_docs_theme.py`
  - Verification: `$ uv run devops ci test tests/config/test_docs_theme.py` passes

## 3. Load the token CSS, the fonts and the SVG favicon

Kind: other. Reads: `zensical.toml`, `src/devops_cli/docs/site.py`, `tests/support/docs_site.py`, `tests/docs/test_site.py`. Changes: `zensical.toml`, `docs/assets/favicon.svg` (new), `tests/docs/test_site.py`.

- [ ] 3.1 Add extra_css to the `[project]` table of `zensical.toml`, above `[project.theme]`, with the four paths docs/assets/css/tokens-base.css, docs/assets/css/tokens-light.css, docs/assets/css/tokens-dark-docs.css and docs/assets/css/site/theme.css, in that order. Set theme.font.text to Source Sans 3, theme.font.code to Source Code Pro and theme.favicon to docs/assets/favicon.svg in `[project.theme]`. Add `docs/assets/favicon.svg` as one vector shape. Keep the three palette entries that follow the system theme. Add the case test_the_stage_carries_the_theme_settings to `tests/docs/test_site.py`, which stages the repository with `src/devops_cli/docs/site.py:def stage_site` into a temporary folder and asserts that the staged config holds the four extra_css paths, the two font settings, the favicon and the slate palette, and that each CSS path is a file of the stage
  - Verification: `$ uv run devops ci test tests/docs/test_site.py` passes

## 4. Scan the docs theme tree in the constructs row

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `tests/gate/construct_gate.py`, `.pre-commit-config.yaml`, `tests/invariants/test_construct_gate_check.py`. Changes: `src/devops_cli/config/constants.py`, `.pre-commit-config.yaml`, `tests/invariants/test_construct_gate_check.py`.
Adds: `test_the_scan_roots_hold_the_docs_theme_tree`

- [ ] 4.1 `tests/invariants/test_construct_gate_check.py`: the case `test_the_scan_roots_hold_the_docs_theme_tree` fails first, because `CONST_AST_GREP_SCAN_ROOTS` holds `src` and `tests` only
  - Verification: `$ uv run devops ci test tests/invariants/test_construct_gate_check.py` fails on the base
- [ ] 4.2 Add the docs theme folder to `CONST_AST_GREP_SCAN_ROOTS` in `src/devops_cli/config/constants.py`, so `CONST_AST_GREP_SCAN_ARGS` and the `constructs` row read the three roots. Change the ast-grep-scan entry of `.pre-commit-config.yaml` to the same three roots, because the gate compares the hook command with that constant. Add the case `test_the_scan_roots_hold_the_docs_theme_tree` to `tests/invariants/test_construct_gate_check.py`: it builds the small tree from `CONST_AST_GREP_SCAN_ARGS`, asserts that the constant holds the docs theme root beside `src` and `tests`, and asserts that the tree reports no escape, so it starts no program
  - Verification: `$ uv run devops ci test tests/invariants/test_construct_gate_check.py` passes

## 5. Hold the docs theme CSS to the color literal rule

Kind: manifest. Reads: `.ast-grep/rules/css-color-literal.yml`, `tests/gate/construct_gate.py`, `tests/invariants/test_construct_gate_check.py`. Changes: `.ast-grep/rules/css-color-literal.yml`, `tests/gate/construct_gate.py`, `tests/invariants/test_construct_gate_check.py`.

- [ ] 5.1 `tests/invariants/test_construct_gate_check.py`: the case `test_every_construct_gate_escape_is_reported[css-rule-files-narrowed]` fails first, because `CONST_DESIGN_CSS_FILES` holds the package CSS folder only, so a rule file that names that folder alone reports no escape while the case expects the message that names the docs theme glob too
  - Verification: `$ uv run devops ci test tests/invariants/test_construct_gate_check.py` fails on the base
- [ ] 5.2 Add the glob `docs/assets/css/site/**` to the `files` of `.ast-grep/rules/css-color-literal.yml` and to `CONST_DESIGN_CSS_FILES` in `tests/gate/construct_gate.py`, beside the package glob `src/devops_cli/design/css/**`. Add the `Violation` of the rule in the tree `docs/assets/css/site` to `VIOLATIONS`, with the CSS source of the existing entry and the suffix `.css`, and map that tree to `src` in `_OTHER_TREE`, so its twin file sits outside the rule. Add the case `css-rule-files-narrowed` to `_CONSTRUCT_GATE_ESCAPES`, which writes the rule file with the package glob alone and expects the message that names both globs. The case starts no program: it writes its own rule file into the small tree and calls `construct_gate_escapes` with canned input, as the other cases do (`tests/invariants/test_construct_gate_check.py:4:(#2164). These cases give it a small tree and the names of its tracked files, so git and ast-grep`). The scan of the committed docs theme CSS is the job of the `constructs` row, which runs `ast-grep scan` over the scan roots (`tests/gate/construct_gate.py:244:["ast-grep", "scan", "--json=compact", *CONST_AST_GREP_SCAN_ROOTS],`) and reads the rule files and the violation table in `tests/gate/construct_gate.py:def problems`
  - Verification: `$ uv run devops ci test tests/invariants/test_construct_gate_check.py` passes

## 6. Check the layout of the built site in the Docs Site Build

Kind: other. Reads: `.github/workflows/docs-site.yml`, `docs/DESIGN.md`. Changes: `.github/workflows/docs-site.yml`, `.github/scripts/docs_theme_check.py` (new).

- [ ] 6.1 Add `.github/scripts/docs_theme_check.py`. It serves the built site folder that the build writes under the store of the runner over a local port, opens three pages in Chromium at 400 px and 1280 px, once with the light scheme and once with the dark scheme, and fails when a page scrolls to the side or a text pair is under 4.5:1. Add two steps to the docs-site job of `.github/workflows/docs-site.yml` after the build step: `uv run --with playwright playwright install --with-deps chromium`, then `uv run --with playwright python .github/scripts/docs_theme_check.py` with the built site folder as its argument. The step proves that no page scrolls to the side and each text pair reaches 4.5:1 in both schemes
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## 7. State the docs theme rules in the design and SDLC documents

Kind: other. Reads: `docs/DESIGN.md`, `docs/SDLC.md`, `.ast-grep/rules/css-color-literal.yml`, `zensical.toml`. Changes: `docs/DESIGN.md`, `docs/SDLC.md`.

- [ ] 7.1 Add the dark-docs.json row to the token pipeline table of `docs/DESIGN.md` at `docs/DESIGN.md:32:| Config | Source | Selector | Outputs |` and say that the docs dark file takes the slate selector. Replace the ast-grep bullet at `docs/DESIGN.md:76:rejects a hex color, a call of a CSS color function` with the tree that the rule covers now, and rewrite the Docs site row at `docs/DESIGN.md:254:The breakpoints are 40rem and 75rem` to the merged state: the theme CSS, the docs dark token file, the three Source faces, the focus outline, the code roles, the breakpoints, the caption classes, the SVG favicon and the layout check. Name the three scan roots of the ast-grep-scan hook in `docs/SDLC.md` beside `docs/SDLC.md:159:H7[ast-grep scan & test]`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 7.2 Edit `docs/DESIGN.md` and `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 5: The ast-grep rule finds 0 color literals in `docs/assets/css/style.css`.
- Group 6: A headless browser check of 3 pages, in both themes, at 400 px and 1280 px width, shows no sideways page scroll and every text pair at 4.5:1 or more.
- Group 3: With no `data-theme` set, the page follows `prefers-color-scheme`.
- Group 6: The Docs Site Build check passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
