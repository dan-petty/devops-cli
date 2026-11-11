# Design spec

This spec sets the look of every devops-cli artifact: the docs site, the README and the generated docs, the Grafana dashboards, the start page, the reports, the HTML artifacts of agents, the charts, the Mermaid diagrams, the terminal output and the Markdown of issues and pull requests. One set of design tokens holds the values. [ADR 0024](adr/0024-the-project-owns-its-design-tokens-in-the-dtcg-format-and-style-dictionary-builds-them.md) records the base and the pipeline. Tracker #4735 holds the items that apply the spec to each target, and the section [Rules for each target](#rules-for-each-target) names the open issue of each target.

## Base and influence

- **Tokens.** The project owns its tokens in the W3C Design Tokens (DTCG) format 2025.10. The values come from open specs.
- **Layout.** The layout model of Tufte CSS 1.9.0: a reading column, margin notes and wide figures.
- **Look.** Measured traits of the Google SRE books and of sre.google: an editorial, calm page that holds much information, with much white space. Headings have the regular weight. The reading text is 18 px on a 28.8 px line. Tables are rules and measured numbers. A caption "Figure N-M." is below each figure, and a caption "Table N-M." is above each table. Diagrams use few colors.
- **Practice.** The SRE practice gives the dashboard and report patterns: the SLO panel, the error budget, the multiwindow burn rate with one page line for each window, the four golden signals, toil, capacity and the postmortem outline.
- **Type.** The Adobe Source family (OFL-1.1): Source Serif 4, Source Sans 3 and Source Code Pro.
- **Not used.** The colors of the Google logo, Google marks and logos, and the Google Sans and Product Sans fonts. No artifact looks like a Google product or page.

## Token pipeline

### Sources

`design/tokens/` holds three token files in the DTCG format 2025.10. Each file has the `$schema` `https://www.designtokens.org/schemas/2025.10/format.json`. No file refers to another file.

| File | Tokens | Holds |
| :--- | ---: | :--- |
| `base.tokens.json` | 50 | Fonts, sizes, spacing, widths, breakpoints, radii, motion, chart strokes, and the two categorical colors that are the same in both themes |
| `light.tokens.json` | 38 | The colors of the light theme |
| `dark.tokens.json` | 38 | The colors of the dark theme, with the same names as the light theme |

Each color token holds its contrast rule in `$extensions.devops-cli.contrast`: `on` names the backgrounds, and `min` is the lowest WCAG 2.x ratio. A rule with `grafana: true` also holds on the four Grafana backgrounds `#ffffff`, `#f4f5f5`, `#181b1f` and `#111217`.

### Build

Style Dictionary, at the version of its lock, builds the tokens. `make design-tokens` runs one build for each config of `design/sd/`. Each config sets `log.warnings` to `"error"`, uses the transform group `css`, and uses only the built-in formats `css/variables` (with `outputReferences: true`) and `json/flat`. The group `web` is not used, because it writes `0.5rem` as `0.5px` in `json/flat`.

| Config | Source | Selector | Outputs |
| :--- | :--- | :--- | :--- |
| `base.json` | `base.tokens.json` | `:root` | `tokens-base.css`, `tokens-base.json` |
| `light.json` | `light.tokens.json` | `:root` | `tokens-light.css`, `tokens-light.json` |
| `dark.json` | `dark.tokens.json` | `@media (prefers-color-scheme: dark)` with `:root:not([data-theme="light"])` | `tokens-dark.css`, `tokens-dark.json` |
| `dark-explicit.json` | `dark.tokens.json` | `:root[data-theme="dark"]` | `tokens-dark-explicit.css` |

The build writes each CSS file to `docs/assets/css/` for the docs site, because Jekyll cannot run the build. It writes each CSS file and each JSON file to `src/devops_cli/design/` as package data. `src/devops_cli/design/css/` holds the hand-written CSS of the package, which reads only token variables. The outputs are in git. Do not edit an output by hand. The build gives 88 CSS variables: 50 base and 38 for each theme.

A page selects its theme with the CSS files: `tokens-light.css` on `:root`, `tokens-dark.css` when the system theme is dark and the page sets no `data-theme="light"`, and `tokens-dark-explicit.css` when the page sets `data-theme="dark"`. Set `color-scheme` with the theme, so that form controls and scroll bars agree.

### Install Style Dictionary

The devcontainer image holds `style-dictionary` on `PATH`. `src/devops_cli/tools_lock/style-dictionary/` holds the lock. On another host, install the lock outside the checkout and give the program to `make`:

```bash
mkdir -p "$HOME/.local/share/style-dictionary"
cp src/devops_cli/tools_lock/style-dictionary/package.json src/devops_cli/tools_lock/style-dictionary/package-lock.json "$HOME/.local/share/style-dictionary/"
npm ci --ignore-scripts --prefix "$HOME/.local/share/style-dictionary"
make design-tokens STYLE_DICTIONARY="$HOME/.local/share/style-dictionary/node_modules/.bin/style-dictionary"
```

Renovate opens a pull request for each new release of Style Dictionary, and the CI job "Design Tokens" fails when the release changes an output. The lock is no entry of `tools.lock`, so `devops install-tools` does not install it, and the `audit` row of `devops ci` does not audit it (#4777).

### Read the tokens in Python

`devops_cli.design.tokens(mode)` gives the tokens of the theme `light` or `dark`: the base tokens and the colors of the theme, by the CSS variable name without `--`, such as `color-bg` or `breakpoint-md`. The module also holds the dash patterns of chart lines (`SERIES_DASHES` and `REFERENCE_DASH`), because DTCG has no token type for them.

### Change a token

1. Edit the token in `design/tokens/`. A color token in a theme file needs the same name in the other theme file.
2. Run `make design-tokens`.
3. Run `uv run pytest tests/design`.
4. Commit the source and the outputs together.

### Checks

- **The CI job "Design Tokens"** runs on a pull request that changes a file of its path filter: `design/`, the lock, `src/devops_cli/design/`, `docs/assets/css/`, `k8s/startpage/`, `k8s/monitoring/dashboards/`, `.github/labels.yml`, the `Makefile` or `ci.yml`. It installs the lock, runs `make design-tokens`, fails when an output is not the build, and runs `tests/design`. It takes less than 1 minute.
- **`tests/design`** checks with coloraide:
  1. The light and the dark theme hold the same names in the sources, in the flat JSON and in each CSS file.
  2. Each contrast rule holds in both themes: 37 rules for each theme, 74 in total.
  3. The categorical colors pass the gates of [Categorical colors](#categorical-colors).
  4. The sequential ramp has a monotonic lightness (`L*`), and the diverging ramp is red at step 1 and blue at step 9 in both themes.
  5. Each width in an `@media` rule of this spec and of the CSS of the package is `breakpoint.md` or `breakpoint.lg`.
  6. The dash patterns of the package are the patterns of [Line patterns](#line-patterns).
- **The ast-grep rule `css-color-literal`** rejects a hex color, a call of a CSS color function and a CSS named color in the hand-written CSS of `src/devops_cli/design/css/`. The docs site item (#4745) and the start page item (#4598) extend the rule to their CSS when they remove its color literals.

## Palette

WCAG 2.x contrast on the built values, computed by coloraide. Each cell gives the hex value, then the ratio on `color.bg` and on `color.surface`.

| Token | Use | Light | Dark | Needs |
| :--- | :--- | :--- | :--- | :--- |
| `color.bg` | Page and chart background | `#ffffff` | `#151514` | - |
| `color.surface` | Code blocks, callouts, the band of SLO tiles | `#f6f6f3` | `#1f1f1d` | - |
| `color.border` | Rules and grid lines only | `#dcdcd6` | `#3b3b37` | No ratio |
| `color.border-strong` | Control borders, chart axes | `#86867f` 3.66 / 3.38 | `#7a7a73` 4.23 / 3.82 | 3:1 |
| `color.fg` | Body text, a single chart series | `#1c1c1a` 17.07 / 15.76 | `#e8e8e3` 14.86 / 13.43 | 4.5:1 |
| `color.fg-muted` | Secondary text, captions, ticks | `#5f5f59` 6.43 / 5.94 | `#a9a9a1` 7.72 / 6.98 | 4.5:1 |
| `color.accent` | Links, focus, a highlighted series | `#0b6e8a` 5.81 / 5.37 | `#78c5da` 9.39 / 8.49 | 4.5:1 |
| `color.status.ok` | State OK | `#007a5e` 5.32 / 4.92 | `#3dc9a0` 8.75 / 7.91 | 4.5:1 |
| `color.status.warn` | State Warn | `#946200` 5.24 / 4.84 | `#f0c04e` 10.75 / 9.71 | 4.5:1 |
| `color.status.error` | State Fail | `#b3261e` 6.54 / 6.04 | `#ff7a66` 7.16 / 6.47 | 4.5:1 |

- `color.status.info`, `color.data.neutral` and `color.syntax.comment` have the value of `color.fg-muted`. Info is neutral, not blue.
- `color.focus` has the value of `color.accent`. Focus is a 2 px outline with a 2 px offset.
- Each status has a tint for its background: `color.status.ok-bg`, `color.status.warn-bg` and `color.status.error-bg`. The status color on its tint has 4.62:1 or more in the light theme and 6.05:1 or more in the dark theme.
- Code on `color.surface`: a comment is `color.syntax.comment` in italics, a string is `color.syntax.string` (the accent), and a keyword is `color.syntax.keyword` (the foreground) in the weight 600. All other code is `color.fg`.
- The lowest ratios: text 4.84:1 (light warn on surface) and 6.47:1 (dark error on surface); other marks 3.38:1 (light border-strong on surface) and 3.82:1 (dark border-strong on surface).
- Light warn and error are 4.0 apart (CIEDE2000) for a reader with deuteranopia. Thus each status shows a shape and a word, and color is never the only sign of a state.

## Chart palettes

Color vision deficiency is simulated with the method of Machado 2009 at severity 1.0 for protanopia, deuteranopia and tritanopia. Distances are CIEDE2000, and OKLab x 100 as the second metric.

### Categorical colors

A categorical color shows the identity of an entity. A chart has at most 3 colored series, in a fixed order, plus "Other". The colors are never cycled, and a color follows its entity across charts.

| Slot | Token | Light | Dark | Use |
| :--- | :--- | :--- | :--- | :--- |
| Series 1 | `color.data.cat.1` | `#a463f2` | `#a463f2` | Every target, Grafana too |
| Series 2 | `color.data.cat.2` | `#e7298a` | `#e7298a` | Every target, Grafana too |
| Series 3 | `color.data.cat.3` | `#002d9c` | `#82cfff` | Targets that follow the theme; not Grafana |
| Other | `color.data.neutral` | `#5f5f59` | `#a9a9a1` | Other, baseline and context |

A single series uses `color.fg`. One highlighted series uses `color.accent`, and its context uses `color.data.neutral`. The status colors are not categorical colors.

The gates of a categorical color:

- chroma 0.10 or more (OKLCh);
- 3:1 or more on `color.bg` and `color.surface` of its theme, and series 1 and 2 also on the four Grafana backgrounds;
- 15 or more (CIEDE2000) from each color of the Google logo;
- 15 or more from each status color, and 8 or more from warn and error under each simulated deficiency;
- 10 or more from "Other" under normal vision and each simulated deficiency.

The gates of the set: each pair 12 or more (CIEDE2000) under normal vision and each simulated deficiency; OKLab 15 or more under normal vision and 8 or more under each simulated deficiency.

The set has 3 colors because no set of 4 colors passes all gates in the light theme with the same hue family in each slot of both themes. Put a 4th entity in "Other", in small multiples or in a table.

### Line patterns

Color is never the only channel. Each line series has its dash pattern, and a reference line has a pattern that no series uses. Points use a circle, a square and a triangle. Bars have direct labels.

| Line | Dash array (px) | Use |
| :--- | :--- | :--- |
| Series 1 | `solid` | The first series, 1.5 px |
| Series 2 | `6 3` | The second series, 1.5 px |
| Series 3 | `8 3 2 3` | The third series, 1.5 px |
| Reference | `2 2` | Thresholds, targets and SLO lines, 1 px |

### Sequential ramp

The sequential ramp shows a magnitude: cividis in 9 steps, `color.data.seq.1` to `color.data.seq.9`. Step 1 is the lowest value. The light theme runs from `#fee838` to `#00224e`, and the dark theme runs from `#00224e` to `#fee838`, so the highest value has the most contrast (15.69:1 and 14.63:1). The lightness (`L*`) is monotonic. Adjacent steps are 7.0 or more apart (CIEDE2000) under each vision.

The faint end has 1.25:1 (light) and 1.16:1 (dark), so a heatmap prints its values or has a data table. Ordered series, such as p50, p95 and p99, use steps 5, 7 and 9 with direct labels. Vega names the ramp `cividis`, and Grafana names it `continuous-cividis`.

### Diverging ramp

The diverging ramp shows a polarity: 9 steps, `color.data.div.1` to `color.data.div.9`. Step 1 is worse (red), step 5 is no change (near the background) and step 9 is better (blue), in both themes.

- Light: ColorBrewer RdBu, reversed. The center has 1.07:1, and the ends have 6.87:1 and 5.90:1.
- Dark: Crameri berlin, reversed. The center has 1.05:1, and the ends have 10.30:1 and 8.80:1.

Use the ramp only where red means worse, such as more latency or more errors. Grafana has no diverging mode: show a change as a line around zero.

### Status in charts

Only an abnormal state gets a status color: the warn and error threshold lines. Status OK is never a series or a line. A page line uses `color.status.error`, a ticket line uses `color.status.warn`, and the line of the 1x budget pace uses `color.fg-muted`.

### Grafana

Grafana does not change a hex color with its theme. Series 1 and 2 use the hex values of `tokens-base.json`, which pass on the four Grafana backgrounds (3.41:1 or more). A third entity uses the Grafana color `text` as the baseline or "Other". More series use the mode `shades` of `text`, or a table. A status uses a Grafana color name that changes with the theme: OK is `text`, Warn is `semi-dark-orange` and Fail is `red`. Heatmaps use `continuous-cividis`. A reader with a color vision deficiency can select the Grafana theme `deut_prot` or `tritanopia`.

## Type

| Face | Use |
| :--- | :--- |
| Source Serif 4 | Reading text of reports and docs pages |
| Source Sans 3 | Headings, navigation, tables, captions, chart text, buttons and HTML dashboards |
| Source Code Pro | Code, identifiers, hashes and commands |

Grafana keeps its own fonts, because it has no font setting. The terminal uses the font of the user.

**Delivery.** Each web target loads the fonts through the Google Fonts css2 API: Source Sans 3 400 and 600, Source Serif 4 with the optical sizes 8 to 60 at 400 and 600, and Source Code Pro 400 and 600, with `display=swap`. The CSP of agent artifacts permits only that font host. Each font stack has system fonts after the Source face.

| Token | Size | Line height | Weight | Use |
| :--- | ---: | ---: | ---: | :--- |
| `font.size.3xl` | 36 px | 1.2 | 400 | `h1`, the report title |
| `font.size.2xl` | 28 px | 1.2 | 400 | `h2`: the size, not the weight, shows the heading level |
| `font.size.xl` | 22 px | 1.2 | 600 | `h3` |
| `font.size.lg` | 18 px | 1.6 | 400 | Reading text (serif) at 40rem and wider |
| `font.size.md` | 16 px | 1.6 | 400 | Reading text (serif) under 40rem; figure titles in sans at 600 |
| `font.size.sm` | 14 px | 1.4 | 400 | Tables, captions, notes, legends and footnotes (sans) |
| `font.size.xs` | 12 px | 1.4 | 400 | Chart ticks and axis titles only; no text is smaller |

Code blocks are 14 px on a 1.5 line, and inline code is 0.875 em.

- **Weights.** 400 for text, `h1` and `h2`. 600 for `h3`, table headers, figure titles and the label "Figure N-M.". Tables use no italics for emphasis. Italics are only for code comments and the caption line in Markdown.
- **Numbers.** Each numeric cell, stat and tick uses `tabular-nums lining-nums`. Numbers align right with fixed decimals in each column. Write `,` as the thousands separator, the minus sign U+2212 for a negative value, and a no-break space between a number and its unit ("212 ms", "99.9 %"). Write a multiplier with no space and the sign U+00D7 ("14.4×"). Use IEC prefixes for bytes (KiB, MiB, GiB), ISO 8601 dates and 24-hour UTC times ("14:00 UTC").
- **Case.** Use sentence case for each heading, title, panel title, axis title, legend, form label and table header. Do not use all capitals, but for acronyms and unit symbols.
- **Measure.** Reading text is 40rem wide (about 70 characters). Figures and tables are up to 60rem wide.
- **Status marks.** On web pages, a status mark is an inline SVG shape, not a font glyph: web fonts do not have all mark glyphs.

## Spacing and layout

- **Spacing.** A 4 px base, in rem tokens: `space.1` 4, `space.2` 8, `space.3` 12, `space.4` 16, `space.6` 24, `space.8` 32, `space.12` 48 and `space.16` 64 px. The paragraph gap is `space.4`. An `h2` has `space.16` above it, a 1 px rule and `space.6` padding (the section rule of the SRE books). An `h3` has `space.8` above it. Figures and tables have a `space.8` margin. Table cells have `space.2` above and below and `space.4` on the right.
- **Widths.** The side gutter is `size.gutter` (16 px) at each width, plus the safe-area insets. The reading column is `size.measure` (40rem). Figures and tables are `size.wide` (60rem). The page frame and dashboards are `size.full` (72rem). Margin notes are `size.margin` (15rem).
- **Breakpoints.** `breakpoint.md` (40rem): the body text changes from 16 px to 18 px. `breakpoint.lg` (75rem): the margin notes get their column (40rem text, a `space.12` gap, 15rem notes). An `@media` rule cannot read a custom property, so CSS writes the literals, and a test compares them with the tokens:

```css
@media (min-width: 40rem) { /* breakpoint.md */ }
@media (min-width: 75rem) { /* breakpoint.lg */ }
```

- **Phone (under 40rem).** One column. Margin notes are inline with a 2 px rule on the left. Tables, code and static SVG charts scroll to the side in their own box (`tabindex="0"`, `role="region"` and a label). A static chart keeps `size.chart-min` (40rem), so its 12 px text does not shrink. Captions stay outside the scroll box. Legends go above the chart. SLO tiles wrap to 2 in each row.
- **Wide screen.** Content stops at `size.full`. More width is white space. Text does not stretch.
- **Targets.** Each interactive element is `size.target` (24 px) or larger (WCAG 2.2, success criterion 2.5.8).
- **Surfaces.** `color.bg` for the page and charts. `color.surface` for code blocks, callouts and the band of SLO tiles. `radius.none` for figures, tables, tiles and charts. `radius.sm` (2 px) for buttons, inputs and inline code. No shadows. Rules are 1 px. Only the focus outline and the rule under a table header are 2 px.
- **Motion.** `motion.duration.fast` (120 ms) with `motion.easing.standard`, only for hover and a change of theme, and only in `prefers-reduced-motion: no-preference`. Charts do not move.
- **Grafana layout** (24 columns). Row 1: the SLO tiles (SLO target, SLI over the window, error budget left, burn rate now), each `w6 h4`. Row 2: the burn rate (`w12 h8`) and the budget left over the window (`w12 h8`). Then one row of golden signals in the order of the book (latency, traffic, errors, saturation), `w12 h8` each, two in each row. Then collapsed rows for capacity, toil and details.

## Chart rules

| Rule | Name | Rule text |
| :--- | :--- | :--- |
| C1 | Form | One message in each chart. A line for change over time, a bar or a dot for a comparison, a stat for one number and a table for exact values. No pie with more than 3 parts, no 3D and no two y-axes. |
| C2 | Title and subtitle | The figure title states the finding in sentence case ("The 6 h burn rate crossed its 6x page line once in 48 hours"). The subtitle gives the SLO or the measure, the window and the step, n, the source, and "illustrative data" when the data is not measured. A dashboard panel title names the signal and the measure ("Latency: p95 of successful requests"). |
| C3 | Captions | "Figure \<section\>-\<n\>." is below the figure. "Table \<section\>-\<n\>." is above the table, outside its scroll box. A caption tells how to read the chart and where the data comes from. GitHub removes `figure` and `figcaption`, so in GitHub Markdown the figure caption is an italic line below the image, and the table caption is a bold line above the table. |
| C4 | Axes and units | Each value axis has a title with its unit in parentheses ("Burn rate (x)", "Latency, p95 (ms)"). 3 to 5 ticks on round numbers. Ticks are 12 px in `color.fg-muted`. The axis line is `color.border-strong`. |
| C5 | Zero baseline | Bars, columns, areas, rates, ratios and burn rates start at 0. Only a line that shows a level can start at another value, with a labeled axis and a note in the subtitle. A log axis says "log scale". |
| C6 | Ink | Only horizontal grid lines, 1 px in `color.border`. No frame, plot background, gradient, shadow, texture or decoration. Lines are 1.5 px (`chart.stroke.data`). The highlighted series is 2.5 px in `color.accent`. A 2 px gap in `color.bg` is between stacked segments and between bars. |
| C7 | Color | At most 3 colored series (`chart.max-series`), in the order `cat.1` to `cat.3`, plus "Other" in `color.data.neutral`. Color follows the entity. Status colors show only a state. Text never has a series color. Each series has its dash pattern, a direct label at a peak or at the end of the line, and a legend when the chart has 2 or more series. |
| C8 | References | Thresholds, targets and SLO lines are 1 px lines with the dash `2 2` and a direct label at the left end in the plot, so the label stays visible when the chart scrolls on a phone. Labels have a 3 px halo in `color.bg`. Deploys and incidents are vertical 1 px dotted lines in `color.fg-muted` with a label above the plot. |
| C9 | Sample size | Each aggregate states n and the window. Do not show p99 when n is less than 100, or p95 when n is less than 20: print "low sample" and the n. The caption marks each window with n less than 30. |
| C10 | Uncertainty | Show only measured intervals, as a band at `chart.band-opacity` (0.2) or as error bars, and name the method ("95 % CI, bootstrap, 1,000 resamples"). A range from minimum to maximum is not an interval. A benchmark shows the spread next to the median. |
| C11 | Accessibility | An SVG chart has `role="img"` with a `title` and a `desc` that states the message. A data table follows in a `details` element. No information is only in a hover. |
| C12 | SRE patterns | For a 99.9 % SLO over 30 days (SRE workbook, Table 5-8): (a) the SLO panel has four tiles: the SLO target with its window, the SLI over the window, the error budget left in %, and the burn rate now. Each tile shows a 36 px number and a state shape with a word. Budget thresholds: more than 25 % neutral, 0 to 25 % warn, less than 0 % error. (b) The error budget chart shows the budget left (%) over the window, from 100 %, with a dashed line of even burn to 0 % at the end of the window. (c) The burn-rate chart shows the 1 h series against its 14.4x page line (2 % of the budget), the 6 h series against its 6x page line (5 % of the budget), and the 1x line of the budget pace (a ticket on the 3-day window, 10 %). y starts at 0, and the unit is x. Never draw a 1 h series against the 6x line. (d) The golden signals, in the order of the book: latency of successful requests (s; p50, p95 and p99 as sequential steps 5, 7 and 9), traffic (reqps), errors (percentunit, with the SLO line) and saturation (percentunit, with the limit line). (e) Toil: stacked columns of hours each week from zero, 3 categories plus "Other", with labeled totals. (f) Capacity: the lines of use, request and limit, and the headroom as text. Label a projection as a projection. |
| C13 | Terminal charts | A sparkline or a waterfall in the terminal prints the minimum, the maximum and the unit next to its block characters. Color never holds the meaning. |
| C14 | Grafana mapping | Series 2 uses the Grafana dash preset `[10, 10]`. A reference line is a constant query, such as `vector(14.4)`, with a display name, a role color name and the line style `dots`. `fillOpacity` is 0. The legend is a list for 3 series or fewer, else a table with last, mean and max. |

## Table rules

| Rule | Name | Rule text |
| :--- | :--- | :--- |
| T1 | Caption | "Table \<section\>-\<n\>." is above the table, outside its scroll box, in 14 px sans. The caption tells what the table shows, the window in UTC, n and the source. In Markdown, a bold line "Table N." is above the table. |
| T2 | Rules | A 2 px rule in `color.fg` under the header row, and a 1 px rule in `color.border` under each body row. No vertical rules, zebra fill, cell backgrounds or shadows. The radius is 0. |
| T3 | Text | 14 px Source Sans 3 on a 1.4 line. The header is 600 in sentence case. Text aligns left. A cell does not wrap a number. |
| T4 | Numbers | Numbers align right with `tabular-nums lining-nums` and fixed decimals in each column. Write `,` as the thousands separator and the minus sign U+2212. The unit is in the column header, not in the cells ("Latency, p95 (ms)"). A column of changes has a sign ("+2.4", "−8.1"). |
| T5 | Empty and special values | A hyphen-minus `-` for no value in HTML and Markdown. "low sample" with the n when C9 applies. No emoji as data: write "Yes" or "Pass". |
| T6 | State column | In HTML, an inline SVG shape with a word: a circle with a check for "OK", a triangle with "!" for "Warn", a hexagon with "x" for "Fail" and a square with "i" for "Info". In Markdown and the terminal, a text mark with the word. |
| T7 | Width | A table is in a box with `overflow-x: auto` (`tabindex="0"`, `role="region"`, `aria-labelledby` the caption), up to 60rem wide. The page never scrolls to the side. |
| T8 | Markdown alignment | `\| :--- \|` for a text column and `\| ---: \|` for a number column, with spaces, in hand-written and generated files. |
| T9 | Check results | One table format for check results, with the columns Check, Result and Link. |
| T10 | Postmortem | Action items have the columns Item, Type, Owner role, Issue and State. A timeline has the columns Time (UTC) and Event. |

## Rules for each target

Each item applies the spec to its target. The rules of a target are in force when its item merges. A new artifact follows the spec from its first pull request.

| Target | Rules | Item |
| :--- | :--- | :--- |
| Docs site | Link the token CSS of `docs/assets/css/`. `style.css` reads only token variables. The system theme applies until the reader selects a theme. The Source faces replace the current fonts. Add `:focus-visible`. Map the syntax classes of Rouge to the syntax roles of the palette. The breakpoints are 40rem and 75rem. One SVG favicon. | #4745 |
| Mermaid | On github.com: no `init` directive, `classDef`, `style` or hex value, because GitHub draws its own light and dark themes. Use `flowchart`, labels in sentence case, 15 nodes or fewer and one direction. On the docs site: the theme `base`, with the theme variables read from the token CSS variables, drawn again when the theme changes. | #4755 |
| README, docs, issues and pull requests | Headings in sentence case. Table rules T5, T8 and T9. Captions as C3 says. Charts as `<picture>` with a light and a dark SVG source and alt text. GitHub alerts `NOTE`, `WARNING` and `CAUTION` for callouts. Static badges in `5f5f59`. `CHANGELOG.md` stays with release-please. | #4605 |
| Labels | One color for each label family, from the light token hex: priority p0 `color.status.error`, p1 `color.status.warn`, p2 `color.accent`, p3 `color.fg-muted`; the types `cat.1`, `cat.2`, `cat.3` and grays; other families gray. No brand colors. A test checks each label color against the token JSON. | #4652 |
| Grafana | The default theme is `system`. Colors as [Grafana](#grafana) and C14 say. Each panel has a unit (C4, one unit id for each quantity), a title in sentence case and a description. The linter checks the colors and the units of the own dashboards. The dashboards copied from upstream stay as they are published. | #4675, #4762 |
| Service dashboard | The Grafana layout of [Spacing and layout](#spacing-and-layout) and C12: the SLO row, the row of burn rate and budget, the row of golden signals, then the jobs table and the logs. | #3655 |
| Start page | Homepage with the Tailwind color `stone` and no fixed theme, so the theme switch stays. `custom.css` is the token CSS and a short map of the Homepage classes to token variables. The build writes one more CSS file with the selector `html.dark`. | #4598 |
| Reports | One HTML file with the token CSS and the shared `report.css` inline. Charts are pairs of inline SVG (light and dark) that the token selectors switch. The outline: title, byline (version or period, commit, UTC time), a summary of 3 to 5 sentences with numbers, numbered sections with figures and tables, a postmortem section when the period has an incident, and an appendix "Method and data". | #4754, #4679 |
| HTML artifacts of agents | The same token CSS and `report.css` inline, from the package data of `devops_cli.design`. Fonts through Google Fonts. | #4754 |
| Charts in code | Altair with vl-convert, as the optional extra `report`. The Vega-Lite config of each theme reads the tokens and holds no literal color or size. Each chart renders as a light and a dark SVG, with text kept as text. | #4758 |
| Terminal (Rich) | One theme maps the roles to ANSI color names: `status.ok` green, `status.warn` yellow, `status.error` bold red, `status.info` default, `muted` dim, `accent` cyan. Each status prints a mark and a word. One severity map. `NO_COLOR` keeps bold and the words. | #4748, #4760 |
| Terminal (Textual) | The themes `devops-light` and `devops-dark` read the token JSON. Each status dot has a word. | #4748 |
| Terminal charts | C13 applies to each change of a terminal chart. | - |
