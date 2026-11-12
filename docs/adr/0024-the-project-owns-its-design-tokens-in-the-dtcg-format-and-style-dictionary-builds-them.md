# The project owns its design tokens in the DTCG format, and Style Dictionary builds them

The artifacts of devops-cli set their colors, fonts and sizes by hand. The inventory of `main` at 818ac6f3 (2026-11-11) found 8 "success" greens, 4 font stacks, 4 severity maps and 34 hex values in the CSS of the docs site. No check measured contrast or colorblind safety. This record decides the base of the design spec and the pipeline that builds its values. [docs/DESIGN.md](../DESIGN.md) is the spec.

## Status

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0024-the-project-owns-its-design-tokens-in-the-dtcg-format-and-style-dictionary-builds-them.md` names the merge commit. The owner accepted the recommended spec and each recommended answer on 2026-11-11 (tracker #4735). Issue #4738 adds the tokens, their build and the spec. The other children of #4735 apply the tokens to each artifact.

## Context

- The owner asked for one design spec for all artifacts: the docs site, the README and the generated docs, the Grafana dashboards, the start page, the reports, the HTML artifacts, the charts, the Mermaid diagrams, the terminal output and the Markdown of issues and pull requests. The spec prefers an open base. One source holds the design values, and an open tool generates the format of each target through a standard format. The text has WCAG 2.2 AA contrast, the chart palettes are safe for colorblind readers, and each web target has a light and a dark theme.
- The look and the practice of Google SRE are the influence: the editorial look of the SRE books, and the SLO, error budget, burn rate and golden signal patterns. The spec does not use the colors of the Google logo, the Google marks or the Google Sans and Product Sans fonts.
- Three designs were built and judged on 2026-11-11. The consistency judge gave 30 to the owned tokens on open specs, 29 to IBM Carbon and 27 to GitHub Primer. The look judge gave 47, 43 and 38.

## Decision

1. **Owned tokens on open specs.** The project owns three token files in `design/tokens/`, in the W3C Design Tokens (DTCG) format 2025.10: `base.tokens.json` (50 tokens), `light.tokens.json` (38) and `dark.tokens.json` (38). No file refers to another file. The light and the dark file hold the same names. The values come from open sources: the layout model of Tufte CSS 1.9.0, measured traits of the SRE books, the Adobe Source type family (OFL-1.1), cividis, ColorBrewer RdBu and Crameri berlin.
2. **Contrast rules next to the values.** Each color token holds its contrast rule in `$extensions.devops-cli.contrast`: the backgrounds it sits on and its lowest WCAG 2.x ratio. A rule marked `grafana` also holds on the four Grafana backgrounds.
3. **Style Dictionary builds the tokens.** Style Dictionary (Apache-2.0, 5.8.0 when this record was written) builds each target format with its built-in formats only: `css/variables` and `json/flat`, with the `css` transform group. Four JSON configs in `design/sd/` set `log.warnings` to `"error"`. No custom transform and no custom format exist. `make design-tokens` runs the four builds.
4. **Committed outputs.** The outputs are in git, and nobody edits them by hand: the token CSS of the docs site (Jekyll cannot run the build) and the token CSS and flat JSON of the package `devops_cli.design`. The CI job "Design Tokens" builds the tokens and fails when an output is not the build.
5. **The lock and its updates.** `src/devops_cli/tools_lock/style-dictionary/` holds the lock, as OpenSpec has its lock. The devcontainer image and the CI job install it with `npm ci --ignore-scripts`. The lock is no entry of `tools.lock`, so Renovate updates it (decision 9 of #4735), with no minimum release age (CONTRIBUTING.md, "Dependency Versions"). Issue #4777 adds the entry of `tools.lock` when a release has dependencies with no audit finding.
6. **Checks.** `tests/design` checks the name parity of the themes, each contrast rule in both themes, the categorical gates under simulated color vision deficiency, the order of the ramps, the breakpoint literals and the dash patterns. coloraide (MIT) computes the color values. The ast-grep rule `css-color-literal` rejects a color literal in hand-written CSS.

## Considered Options

- **IBM Carbon tokens and IBM Plex.** The artifacts look like IBM pages. The DTCG export of Carbon uses JSON Pointer values that Style Dictionary 5.7.1 cannot resolve: 24 and 29 tokens drop out of the two themes, 5 light names give their light values to the dark theme, and the build fails with warnings set to `"error"`.
- **GitHub Primer primitives.** The artifacts look like GitHub pages. A seed copy cuts the link to upstream, and each upgrade needs 98 edits by hand.
- **A DTCG resolver file for the themes.** Style Dictionary 5.7.1 does not read resolver files, so the file can drift from the configs.
- **Values copied into each target by hand.** This is the state that the inventory measured.

## Consequences

- One edit of a token file and one `make design-tokens` change each web target. Grafana, GitHub Markdown, Mermaid on github.com and the terminal cannot read a token build, so the spec gives them rules and checks.
- The trial build: `npm ci` in 15 s, the build in 6.0 s, 0 warnings, the same bytes over two builds, 88 CSS variables in 4 files (9,336 bytes, 3,849 bytes gzip).
- The only custom code is the package module `devops_cli.design`, about 50 lines, which reads the flat JSON and holds the dash patterns of chart lines.
- Each viewer of a web target sends a request to the Google Fonts css2 API, which serves the Source fonts. The artifact CSP permits only that font host.
- The dependencies of Style Dictionary 5.8.0 have 6 `npm audit` findings (2 low, 4 moderate). The dependency ranges of Style Dictionary do not permit the fixed releases. Style Dictionary reads only the committed files of `design/`, and the package and the Service image do not hold it. Issue #4777 tracks the findings.
