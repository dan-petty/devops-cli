## ADDED Requirements

### Requirement: The docs theme reads only token variables
The hand-written docs theme CSS SHALL set each theme value from a design token variable, and SHALL hold no color literal.

#### Scenario: Each declaration reads a token
- **WHEN** A test reads each declaration of docs/assets/css/site/theme.css
- **THEN** Each custom property takes a var() of a variable that the base, the light or the docs dark token CSS declares, and each color variable of the theme sits under the selectors [data-md-color-scheme="default"] and [data-md-color-scheme="slate"]

#### Scenario: The color literal rule reports no finding
- **WHEN** A developer runs `uv run devops ci --check --only constructs`, which scans the docs theme tree with the rule css-color-literal
- **THEN** The row reports 0 findings

### Requirement: The contrast of each text pair of the docs theme
Each text pair of the docs theme MUST have a contrast of 4.5:1 or more in the light and in the dark scheme.

#### Scenario: Body, muted, link and code pairs in both schemes
- **WHEN** A test resolves the token value of each mapped theme variable in the light and the dark scheme and computes the WCAG 2.2 ratio of body, muted and link text on the page background and of code, comment, string and keyword on the code background
- **THEN** Each ratio is 4.5:1 or more

### Requirement: The slate scheme takes the dark tokens
The docs dark token CSS SHALL apply the dark values when the page sets data-md-color-scheme to slate, and the site SHALL select slate from the system dark preference until the reader picks a theme.

#### Scenario: The dark token selector
- **WHEN** A test reads the docs dark token CSS
- **THEN** The file declares its tokens under the selector [data-md-color-scheme="slate"], which matches the body element of the theme, and the selector holds no :root

#### Scenario: The system dark preference
- **WHEN** The Docs Site Build job runs `uv run python .github/scripts/docs_theme_check.py` on the built site, with the dark color scheme of the browser and no stored choice
- **THEN** The body element of each page that the check opens carries data-md-color-scheme slate, and with the light color scheme it carries default

### Requirement: The three Source faces load
The docs site SHALL load Source Serif 4, Source Sans 3 and Source Code Pro through one request of the Google Fonts css2 API with display=swap, and SHALL set Source Serif 4 on the reading text, Source Sans 3 as the text face of the theme and Source Code Pro as the code face.

#### Scenario: The font request and the font rules
- **WHEN** A test reads the docs theme CSS
- **THEN** The css2 request names Source Serif 4, Source Sans 3 and Source Code Pro with display=swap, --md-text-font takes var(--font-family-sans), --md-code-font takes var(--font-family-mono), and the reading text rule takes var(--font-family-serif)

#### Scenario: One font request on a built page
- **WHEN** A developer runs `uv run devops docs site build --strict`
- **THEN** The build exits 0, and each built page holds no font link of the theme, so the css2 request of the docs theme CSS is the one font request

### Requirement: The focus outline of the docs site
Each focusable element of the docs site SHALL show a 2 px accent outline with a 2 px offset.

#### Scenario: The focus-visible rule
- **WHEN** A test reads the focus-visible rule of the docs theme CSS and the base tokens
- **THEN** The rule sets an outline of var(--border-width-focus) solid var(--color-focus) with an offset of var(--border-width-focus), and the base tokens give that width as 2px

### Requirement: The breakpoints and the caption classes of the docs theme
The docs theme CSS SHALL use only the breakpoints 40rem and 75rem, SHALL set the reading text to the size token font.size.md under 40rem and to font.size.lg from 40rem, and SHALL provide the figure caption class and the table caption class of the design spec.

#### Scenario: Each media query width
- **WHEN** A test reads each media rule of the docs theme CSS
- **THEN** Each width is 40rem or 75rem

#### Scenario: The size of the reading text
- **WHEN** The Docs Site Build job runs `uv run python .github/scripts/docs_theme_check.py` on the built site
- **THEN** The reading text of each page that the check opens is 16 px at the width 400 px and 18 px at the width 1280 px

#### Scenario: The caption class declarations
- **WHEN** A test reads the two caption classes of the docs theme CSS
- **THEN** Each class takes its font size from var(--font-size-sm) and sets color: var(--color-fg-muted), and the table caption class sets a margin below the caption

### Requirement: The syntax roles of the code blocks
The docs theme SHALL give each code class its syntax role: a comment in italics, a string, a keyword at weight 600, and all other code the foreground.

#### Scenario: The syntax declarations
- **WHEN** A test reads the syntax declarations of the docs theme CSS
- **THEN** --md-code-hl-comment-color takes var(--color-syntax-comment) with italics, --md-code-hl-string-color takes var(--color-syntax-string), --md-code-hl-keyword-color takes var(--color-syntax-keyword) at weight 600, and the other code classes take var(--color-fg)

### Requirement: The SVG favicon of the docs site
The docs site SHALL use one SVG favicon in place of the default icon of the theme.

#### Scenario: The favicon of a built page
- **WHEN** A developer runs `uv run devops docs site build --strict`
- **THEN** The build exits 0, and the icon link of each built page names docs/assets/favicon.svg

### Requirement: Each built page links the token CSS and the theme CSS
Each built page of the docs site SHALL link the three token CSS files and then the docs theme CSS.

#### Scenario: A local build
- **WHEN** A developer runs `uv run devops docs site build --strict`
- **THEN** The build exits 0, and each built page links the three token CSS files and then the docs theme CSS

#### Scenario: The site config is valid
- **WHEN** A developer runs `uv run devops gh pages verify`
- **THEN** The command exits 0 for the site config that holds the list of CSS files and the theme settings
