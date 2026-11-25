## ADDED Requirements

### Requirement: The docs theme reads only token variables
The hand-written docs theme CSS SHALL set each theme value from a design token variable, and SHALL hold no color literal.

#### Scenario: Each declaration reads a token
- **WHEN** A test reads each declaration of docs/assets/css/site/theme.css
- **THEN** Each value is a var() of a variable that the base, the light or the docs dark token CSS declares

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

#### Scenario: The dark token selector and the palette
- **WHEN** A test reads the docs dark token CSS and the site config
- **THEN** The dark token file uses the selector :root[data-md-color-scheme="slate"], and the site config names slate for the dark system preference

### Requirement: The three Source faces load
The docs site SHALL load Source Serif 4, Source Sans 3 and Source Code Pro through the Google Fonts css2 API with display=swap, and SHALL set Source Sans 3 as the text face and Source Code Pro as the code face.

#### Scenario: The font settings and the font request
- **WHEN** A test reads the site config and the docs theme CSS
- **THEN** The text font is Source Sans 3, the code font is Source Code Pro, and the css2 request names Source Serif 4, Source Sans 3 and Source Code Pro with display=swap

### Requirement: The focus outline of the docs site
Each focusable element of the docs site SHALL show a 2 px accent outline with a 2 px offset.

#### Scenario: The focus-visible rule
- **WHEN** A test reads the focus-visible rule of the docs theme CSS and the base tokens
- **THEN** The rule sets an outline of var(--border-width-focus) solid var(--color-focus) with an offset of var(--border-width-focus), and the base tokens give that width as 2px

### Requirement: The breakpoints and the caption classes of the docs theme
The docs theme CSS SHALL use only the breakpoints 40rem and 75rem, and SHALL provide the figure caption class and the table caption class of the design spec.

#### Scenario: Each media query width
- **WHEN** A test reads each media rule of the docs theme CSS
- **THEN** Each width is 40rem or 75rem

#### Scenario: The caption class declarations
- **WHEN** A test reads the two caption classes of the docs theme CSS
- **THEN** Each class sets font-size: var(--font-size-sm) and color: var(--color-fg-muted), and the table caption class sets a margin below the caption

### Requirement: The syntax roles of the code blocks
The docs theme SHALL give each code class its syntax role: a comment in italics, a string, a keyword at weight 600, and all other code the foreground.

#### Scenario: The syntax declarations
- **WHEN** A test reads the syntax declarations of the docs theme CSS
- **THEN** --md-code-hl-comment-color takes var(--color-syntax-comment) with italics, --md-code-hl-string-color takes var(--color-syntax-string), --md-code-hl-keyword-color takes var(--color-syntax-keyword) at weight 600, and the other code classes take var(--color-fg)

### Requirement: The SVG favicon of the docs site
The docs site SHALL use one SVG favicon in place of the emoji favicon.

#### Scenario: The favicon setting
- **WHEN** A developer runs `uv run devops docs site build --strict`
- **THEN** The build exits 0, and the site config names one SVG favicon and holds no emoji

### Requirement: Each built page links the token CSS and the theme CSS
Each built page of the docs site SHALL link the three token CSS files and then the docs theme CSS.

#### Scenario: A local build
- **WHEN** A developer runs `uv run devops docs site build --strict`
- **THEN** The build exits 0, and each built page links the three token CSS files and then the docs theme CSS
