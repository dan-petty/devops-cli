# Proposal: #4738

## Why
No file holds the design values of devops-cli. Each artifact sets its colors, fonts and sizes by hand: the inventory of `main` at 818ac6f3 (2026-11-11) found 8 "success" greens, 4 font stacks, 4 severity maps and 34 hex values in the CSS of the docs site. No check measures contrast or colorblind safety. The other children of the design spec tracker #4735 need one source of values to read. Closes #4738.

## What Changes
- `design/tokens/{base,light,dark}.tokens.json`: the tokens in the W3C DTCG format 2025.10 (50, 38 and 38 tokens). Each color token holds its contrast rule in `$extensions.devops-cli.contrast`.
- `design/sd/{base,light,dark,dark-explicit}.json`: four Style Dictionary configs with `log.warnings` `"error"`, the transform group `css` and the built-in formats `css/variables` and `json/flat` only.
- `Makefile`: `make design-tokens` runs the four builds.
- Generated and committed: `docs/assets/css/tokens-*.css`, `src/devops_cli/design/tokens-*.css` and `src/devops_cli/design/tokens-{base,light,dark}.json`. The issue names `src/devops_cli/design/css/` for the package CSS, but the construct gate permits no `ignores` in an ast-grep rule (#1902), so `css/` holds only hand-written CSS, which the rule `css-color-literal` holds.
- `src/devops_cli/design/__init__.py`: `tokens(mode)` reads the package data, and the module holds the dash patterns of chart lines.
- `src/devops_cli/tools_lock/style-dictionary/`: the lock of Style Dictionary 5.8.0. The devcontainer image installs it with `npm ci --ignore-scripts`. Renovate updates it (decision 9 of #4735), with no minimum release age (CONTRIBUTING.md, "Dependency Versions").
- `.github/workflows/ci.yml`: the job "Design Tokens" builds the tokens, fails when a committed output is not the build, and runs `tests/design`, only when a path of its filter changes.
- `tests/design`: name parity, the 74 contrast rules, the categorical gates, the ramps, the breakpoint literals, the dash patterns and the label colors of #4652, with coloraide 8.14.1 as a dev dependency.
- `.ast-grep/rules/css-color-literal.yml`: rejects a color literal in the hand-written CSS of `src/devops_cli/design/css/`, with its entry in the construct gate (`tests/gate/construct_gate.py`). No open pull request changes a CSS file.
- `docs/DESIGN.md` (the spec), ADR 0024, a row in the "Where to look" table of `AGENTS.md`, a line in `docs/index.md`, and the job section of `docs/SDLC.md`.
- `.github/labels.yml` and `.github/workflows/pr-title.yml`: the label `scope/design` and the title scope `design`.
- No consumer changes. The other children of #4735 apply the tokens.
- The package module `devops_cli.design` is a new interface that the next items read, so the change has a spec delta.

## Capabilities
- `design-tokens` (new): the tokens of each theme, their contrast rules and the committed build.

## Impact
- New dev dependency: coloraide 8.14.1 (MIT). New Node tool outside `tools.lock`: Style Dictionary 5.8.0 (Apache-2.0).
- The devcontainer image gets `style-dictionary` on `PATH`. The Service image does not hold it.
- The change fits one pull request.

## Feasibility
- The rule of CONTRIBUTING.md, "Dependency Versions" (owner, 2026-11-11), sets no minimum release age: pin the newest release that fixes the known issues and passes the tests. Style Dictionary 5.8.0 (npm, 2026-11-03) is the newest release. Its lock has 106 packages, each with a sha512 from registry.npmjs.org and no install script, and each with a permissive license read from the lockfile: MIT (69), Apache-2.0 (26), BlueOak-1.0.0 (5), BSD-3-Clause (3), ISC (2) and 0BSD (1). The build with 5.8.0 gives the same bytes as the trial build with 5.7.1.
- coloraide 8.14.1 (PyPI, 2026-11-08) is the newest release, with the MIT license. It computes WCAG 2.1 contrast, the Machado 2009 simulation and CIEDE2000.
- A build in the devcontainer: `npm ci` 4 s, `make design-tokens` 2.0 s, 0 warnings with `log.warnings` `"error"`, the same bytes over two builds, 88 CSS variables (50 base, 38 for each theme).
- `uv run pytest tests/design -n 0`: 15 tests pass in 6.5 s; a light `color.fg` of `#aaaaaa` fails its rule (2.32:1 on bg, 2.15:1 on surface).
- The construct gate scans only `src` and `tests`, refuses `ignores` in a rule, and needs one violation of each rule in its table (`tests/gate/construct_gate.py`). The new rule holds `src/devops_cli/design/css/`, which has no file yet; the shared report stylesheet (#4754) goes there. A scan of `docs/assets/css/` with the rule finds 51 color literals in `style.css`, which the docs site item #4745 removes.
- `npm audit --package-lock-only` of the lock names 6 findings (2 low, 4 moderate) in dependencies of Style Dictionary 5.8.0. The dependency ranges of Style Dictionary do not permit the fixed releases of `glob` and `minimatch`, and `deepmerge` has no fixed release. The lock is no entry of `tools.lock`, so the `audit` row does not audit it; #4777 tracks this.

## Existing Tool Considered
- The W3C DTCG format 2025.10 and Style Dictionary 5.8.0 build each format with built-in formats only. coloraide 8.14.1 computes contrast, colorblind simulation and color distance. ast-grep, which the project uses, holds the CSS rule. Renovate updates the lock.
- Rejected: IBM Carbon tokens (Style Dictionary 5.7.1 cannot resolve its JSON Pointer values: 24 and 29 tokens drop out), GitHub Primer primitives (a seed copy needs 98 edits for each upgrade), and a DTCG resolver file (Style Dictionary 5.7.1 does not read it).
- The only custom code is the module `devops_cli.design`, about 50 lines. Cost: about 150,000 tokens and 1 day.
- The change deletes no internal code.
