## ADDED Requirements

### Requirement: The docs dark token CSS holds the package dark values
The token build SHALL write docs/assets/css/tokens-dark-docs.css from the config design/sd/dark-docs.json under the selector :root[data-md-color-scheme="slate"], and that file SHALL hold the same token names and values as src/devops_cli/design/tokens-dark.css.

#### Scenario: The docs dark file and the package dark file
- **WHEN** A test reads each declaration of the docs dark token CSS and of the package dark token CSS
- **THEN** The docs file holds the slate selector, and each of its 38 token names and values equals the package file
