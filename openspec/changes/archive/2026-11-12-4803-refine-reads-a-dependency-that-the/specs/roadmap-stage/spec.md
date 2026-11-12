## ADDED Requirements

### Requirement: The stage job reads a dependency named by its title
The stage job SHALL leave out an item whose Dependencies section names an open issue by its quoted Conventional Commit title, as it does for `#N`. A title SHALL name the one open Item with that exact title, else the one closed Item with it. A closed issue SHALL hold nothing back.

#### Scenario: An open and a closed issue named by their titles
- **WHEN** one Ready item names an open issue and a closed issue by their quoted titles, and another Ready item names only the closed issue
- **THEN** the job leaves out the first item with the reason that names the open issue, and it stages the second item
