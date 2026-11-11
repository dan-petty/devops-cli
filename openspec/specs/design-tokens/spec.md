# design-tokens Specification

## Purpose
The design tokens are the one source of the colors, fonts and sizes of every devops-cli artifact. The package reads the built tokens of each theme, and each color token holds the contrast rule that it passes.

## Requirements

### Requirement: The package reads the tokens of each theme
`devops_cli.design.tokens(mode)` SHALL return the base tokens and the colors of the theme `light` or `dark`, by the CSS variable name without `--`. The light and the dark theme SHALL hold the same names in the token sources, in the flat JSON and in each built CSS file.

#### Scenario: A theme holds the base tokens and its own colors
- **WHEN** a caller reads `tokens("light")` and `tokens("dark")`
- **THEN** each result holds 88 tokens, with `color-bg` `#ffffff` in the light theme and `#151514` in the dark theme

#### Scenario: The themes hold the same names
- **WHEN** the test compares the names of the light and the dark theme in the sources, the flat JSON and each CSS file
- **THEN** each pair holds the same names

### Requirement: Each color token passes its contrast rule
Each contrast rule that a color token declares in `$extensions.devops-cli.contrast` SHALL hold on the built values of each theme. A rule marked `grafana` SHALL also hold on the four Grafana backgrounds.

#### Scenario: Every declared rule passes
- **WHEN** the test computes the WCAG 2.x ratio of each rule in both themes
- **THEN** 37 rules for each theme pass and none fails

#### Scenario: A token under its minimum fails
- **WHEN** a light `color.fg` of `#aaaaaa` is checked
- **THEN** its rules on `color-bg` (2.32:1) and `color-surface` (2.15:1) fail

### Requirement: The categorical colors stay apart for colorblind readers
The categorical colors of each theme SHALL be 12 or more apart (CIEDE2000) under normal vision and simulated protanopia, deuteranopia and tritanopia, and 15 or more from each status color and each color of the Google logo.

#### Scenario: The gates pass in both themes
- **WHEN** the test computes the distances of the three categorical colors of each theme
- **THEN** each gate passes
