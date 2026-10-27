# Spec Delta

## ADDED Requirements

### Requirement: The documentation site provides an index home page

The repository SHALL maintain `docs/index.md` as the home page that routes visitors to the primary documentation guides. When built, the site root SHALL serve `index.html`.

#### Scenario: The documentation directory includes an index page

- **WHEN** `docs/index.md` is inspected
- **THEN** `docs/index.md` exists as a Markdown file with non-empty content
- **AND** `index.html` is generated at the site root during the build

### Requirement: The documentation site removes source Markdown files

The documentation site settings in `docs/_config.yml` SHALL configure `optional_front_matter.remove_originals: true`. The built site output SHALL contain no raw `.md` files.

#### Scenario: Built site contains no source Markdown files

- **WHEN** `docs/_config.yml` is inspected
- **THEN** `optional_front_matter` sets `remove_originals` to `true`
- **AND** no `.md` files exist in the built site output

### Requirement: Default layout navigation links reach only built pages

The default site layout in `docs/_layouts/default.html` SHALL contain no links to `/ARCHITECTURE.html` or non-existent built pages. Every navigation and footer link SHALL resolve to a built page or external repository target.

#### Scenario: Layout contains no broken Architecture link

- **WHEN** `docs/_layouts/default.html` is inspected
- **THEN** neither header navigation nor footer contains `/ARCHITECTURE.html`
