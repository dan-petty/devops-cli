# Proposal

## Why

The docs site of #4745 does not follow the design spec: its palette, fonts, code colors and favicon do not come from the design tokens, so some text pairs sit below the WCAG 2.2 AA ratio of 4.5:1, the page has no focus style and no scale of breakpoints, and the theme CSS has no caption classes.

## What Changes

- Add `design/sd/dark-docs.json` and its build line in `Makefile`, so the dark token values apply under the Zensical slate scheme.
- Add `docs/assets/css/site/theme.css`, which sets each Zensical theme value from a design token variable and holds no color literal.
- Load Source Serif 4, Source Sans 3 and Source Code Pro through the Google Fonts css2 API with display=swap, and add the focus-visible rule, the 40rem and 75rem breakpoints, the two caption classes and the syntax roles to the theme CSS.
- Set `extra_css` in the `[project]` table of `zensical.toml`, set `theme.font` and `theme.favicon`, and add `docs/assets/favicon.svg` in place of the emoji favicon.
- Add the docs theme folder to the scan roots of the constructs row and to the files of the `css-color-literal` rule, with a case of the gate module and one row of the violation table.
- Add the layout check of the built site to the Docs Site Build workflow, in both schemes at 400 px and 1280 px.
- Add `tests/config/test_docs_theme.py` and a stage case in `tests/docs/test_site.py`.
- State the merged docs theme rules in `docs/DESIGN.md` and the scan roots in `docs/SDLC.md`.
- The change carries a spec delta: a reader of the docs site observes the palette, the fonts, the code colors, the focus outline, the captions and the favicon.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-tokens`: The docs dark token CSS holds the package dark values
- `github-pages`: The docs theme reads only token variables, The contrast of each text pair of the docs theme, The slate scheme takes the dark tokens, The three Source faces load, The focus outline of the docs site, The breakpoints and the caption classes of the docs theme, The syntax roles of the code blocks, The SVG favicon of the docs site, Each built page links the token CSS and the theme CSS
- `ci-gate-rows`: The constructs row scans the docs theme tree

## Impact

- Code: `design/sd/dark-docs.json`, `docs/assets/css/tokens-dark-docs.css`, `Makefile`, `docs/assets/css/site/theme.css`, `zensical.toml`, `docs/assets/favicon.svg`, `src/devops_cli/config/constants.py`, `.pre-commit-config.yaml`, `.ast-grep/rules/css-color-literal.yml`, `.github/workflows/docs-site.yml`, `.github/scripts/docs_theme_check.py`
- Documents: `docs/DESIGN.md`, `docs/SDLC.md`
- Tests: `tests/config/test_docs_theme.py`, `tests/docs/test_site.py`, `tests/invariants/test_construct_gate_check.py`, `tests/gate/construct_gate.py`

## Feasibility

- The issue body asks to rewrite `docs/assets/css/style.css` and to remove the dark default of `docs/_layouts/default.html`. The probes answer, word for word: The path `docs/_layouts/default.html` is no file of the staging commit. Commit 64b71991 2026-11-12 feat(docs): move the docs site to Zensical with a full nav and version (#5183) deleted or renamed it. and The path `docs/assets/css/style.css` is no file of the staging commit. Commit 64b71991 2026-11-12 feat(docs): move the docs site to Zensical with a full nav and version (#5183) deleted or renamed it. Comments 3, 4 and 5 redirect the item to Zensical, so the plan changes no Jekyll file and rewrites no style.css.
- `list_files(docs/assets)` showed only the folder `docs/assets/css`, and `list_files(docs/assets/css)` showed the four generated token files and no theme CSS, so `docs/assets/favicon.svg` and `docs/assets/css/site/theme.css` are new files of this change.
- `read_file(zensical.toml)` showed `zensical.toml:11:site_name = "devops-cli"` in the `[project]` table, `zensical.toml:20:[project.theme]` for the theme keys, and `zensical.toml:50:scheme = "slate"` in the dark palette entry, and the file holds no extra_css, no theme.font and no theme.favicon key.
- `read_file(src/devops_cli/docs/site.py, 294-306)` showed `src/devops_cli/docs/site.py:301: **config,` in `src/devops_cli/docs/site.py:def _staged_config`, which spreads each key of the `[project]` table into the staged config, so extra_css goes in that table, above `[project.theme]`.
- `read_file(design/sd/dark.json)` showed `design/sd/dark.json:12: "buildPath": "docs/assets/css/",` and `design/sd/dark.json:19: "@media (prefers-color-scheme: dark)",` with the data-theme selector on the next line, so the shared dark CSS never matches a Zensical page, which sets data-md-color-scheme, and the docs config copies the same shape.
- `read_file(Makefile, 1-16)` showed `Makefile:11:design-tokens:` with four build lines, the last at `Makefile:15:$(STYLE_DICTIONARY) build -c design/sd/dark-explicit.json`, so no line builds a docs config, and group 1 adds the fifth line.
- `read_file(.github/workflows/ci.yml, 905-935)` showed `.github/workflows/ci.yml:920: run: make design-tokens` and `.github/workflows/ci.yml:933: git diff --exit-code -- docs/assets/css src/devops_cli/design k8s/monitoring/dashboards`. style-dictionary is NOT_IN_RUNNER, so the runner cannot build the tokens: group 1 adds the config to the build and commits the output that the build writes, and the Design Tokens job fails when the committed file is not the build.
- `read_file(tests/support/design_tokens.py, 80-90)` showed `tests/support/design_tokens.py:89:The custom property names, without` in the docstring of `tests/support/design_tokens.py:def css_variables`, so the helper returns names only; the new case reads each declaration with its own regex and calls no helper.
- `read_file(tests/design/test_tokens.py, 50-95)` showed `tests/design/test_tokens.py:89: if (DOCS_TOKEN_CSS_DIR / f"tokens-{file}.css").read_bytes()` over CSS_FILES and `tests/design/test_tokens.py:58: ) == (True, True, {}, 38)` for the 38 dark token names. The docs dark file stays out of CSS_FILES, so that byte case keeps passing, and the count of 38 dark tokens comes from that line.
- `read_file(.ast-grep/rules/css-color-literal.yml)` showed `.ast-grep/rules/css-color-literal.yml:7: - "src/devops_cli/design/css/**"` as the only entry of files, and the rule holds no ignores key.
- `read_file(tests/gate/construct_gate.py, 75-215)` showed `tests/gate/construct_gate.py:84:CONST_DESIGN_CSS_FILES: Final[tuple[str, ...]] = ("src/devops_cli/design/css/**",)`, `tests/gate/construct_gate.py:97: "css-color-literal": CONST_DESIGN_CSS_FILES,`, `tests/gate/construct_gate.py:205: held.setdefault(violation.rule, []).append(f"{violation.tree}/**")`, `tests/gate/construct_gate.py:326: if files and data.get("files") != files:` and `tests/gate/construct_gate.py:328: if "ignores" in data:`, so the rule files, the violation table and the scan roots are three lists that must agree.
- `read_file(tests/gate/construct_gate.py, 424-475)` showed `tests/gate/construct_gate.py:244:["ast-grep", "scan", "--json=compact", *CONST_AST_GREP_SCAN_ROOTS],` inside `tests/gate/construct_gate.py:def reported_rules` and `tests/gate/construct_gate.py:461: scan = scan_problems(reported_rules(Path(scratch)))` inside `tests/gate/construct_gate.py:def problems`, so the ast-grep program starts in the `constructs` row only, and each pytest case of the gate check passes canned output.
- `read_file(src/devops_cli/config/constants.py, 5155-5190)` gave `src/devops_cli/config/constants.py:5169:CONST_AST_GREP_SCAN_ROOTS: Final[tuple[str, ...]] = ("src", "tests")`, a set of 2 members, and `src/devops_cli/config/constants.py:5174: *CONST_AST_GREP_SCAN_ROOTS,` inside CONST_AST_GREP_SCAN_ARGS. Each member is decided: src and tests stay, and the docs theme folder is added, for 3 members.
- `read_file(.pre-commit-config.yaml, 78-95)` showed `.pre-commit-config.yaml:88: entry: env UV_MALWARE_CHECK=0 uv run ast-grep scan --error=unused-suppression --error=no-suppress-all src tests`, and the gate compares that entry with the scan-root constant, so the hook entry takes the third root with the constant.
- `read_file(.github/workflows/docs-site.yml, 1-80)` showed `.github/workflows/docs-site.yml:15: - "docs/**"` and `.github/workflows/docs-site.yml:24: - "zensical.toml"` in the paths filter, and `.github/workflows/docs-site.yml:71: run: uv run devops docs site build --strict`. So the Docs Site Build check runs the real build on this pull request, and group 6 adds the layout step to that job.
- The headless criterion of the issue maps to group 6 and not to a person: Playwright and Chromium are NOT_IN_RUNNER, and the Docs Site Build job is the only place of this pull request that builds the site and can open it in a browser.
- Preconditions of the functions the plan calls: `src/devops_cli/docs/site.py:def stage_site` needs a checkout of the repository and writes the stage; `src/devops_cli/docs/site.py:def read_site_config` needs a checkout; `src/devops_cli/docs/site.py:def read_build_data` needs a checkout and runs git; `src/devops_cli/docs/site.py:def build_site` needs a checkout and the zensical program, which `src/devops_cli/docs/site.py:233: require_binary(_ZENSICAL, install_hint=_ZENSICAL_INSTALL_HINT)` requires on PATH.
- Runner capabilities of each command and program the plan introduces: `uv run devops ci test` runs uv and pytest of the image, failure class test; `uv run devops ci --check --only constructs` runs devops, ast-grep and the gate module of the image, failure class constructs; `uv run devops ci --check --only actionlint,zizmor` runs actionlint and zizmor of the image, failure class lint; `uv run devops ci docs` runs devops of the image, failure class docs. zensical is NOT_IN_RUNNER (it comes from the docs dependency group, `pyproject.toml:146: "zensical==0.1.3",`), style-dictionary is NOT_IN_RUNNER, and playwright with Chromium is NOT_IN_RUNNER; only the Docs Site Build workflow installs them. The pod sets readOnlyRootFilesystem true, runAsNonRoot true and drops all capabilities.
- A model review found that the case of group 5 ran an ast-grep scan inside `tests/invariants/test_construct_gate_check.py`. The finding is right, and group 5 corrects it: `read_file(tests/invariants/test_construct_gate_check.py, 1-6)` showed `tests/invariants/test_construct_gate_check.py:1:"""The construct gate check reports every escape of a committed tree, with no program started.` and `tests/invariants/test_construct_gate_check.py:4:(#2164). These cases give it a small tree and the names of its tracked files, so git and ast-grep`, and `read_spec(ci-gate-rows, "A check of committed files is a row, not a pytest test")` gave `No pytest test SHALL start ruff, ast-grep, kubectl kustomize or a fresh Python interpreter to check a committed file or a configuration.` So the new case `css-rule-files-narrowed` writes its own rule file into the small tree and calls `construct_gate_escapes` with canned input, and the scan of the committed docs theme CSS stays with the `constructs` row.
- Not checked by a tool of this run: that Zensical 0.1.3 accepts extra_css in the `[project]` table, theme.font.text, theme.font.code and theme.favicon, and that it sets data-md-color-scheme to slate from the system dark preference. The first checks against the real system are `uv run devops docs site build --strict` on a checkout with the docs dependency group, `uv run devops gh pages verify`, and the layout step `uv run --with playwright python .github/scripts/docs_theme_check.py` over the built site.

## Existing Tool Considered

Zensical 0.1.3 (MIT, in use since #5183) supplies the palette that follows prefers-color-scheme with a reader toggle, the theme variables, the font and favicon settings, the breakpoints, the focus styles and the code block classes; Playwright (Apache-2.0) supplies the headless browser of the layout check; Style Dictionary builds the token CSS; the Google Fonts css2 API serves the three Source faces. The token map, the docs dark token file, the caption classes and the ast-grep rule stay custom: about 40k tokens and 2 hours to build, keep and fix.

## Dependencies

- #4738: it delivers the design tokens, their build and the design spec that this change maps, and its build writes the token CSS files that the docs theme reads.
