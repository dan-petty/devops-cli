## Context

The scope of a title gives the label `scope/<scope>` when `.github/labels.yml` declares it. Intake and `devops pr create` share this rule. A scope with no label gets a warning and no label. PR #2821 declared `scope/git` only, and the warning came back for `agents`.

## Decisions

- **Gate the title, not the label.** The `Semantic PR title` check already runs on every pull request into `main`, and it already holds the form of the title. Its `scopes` input holds the vocabulary. An author who needs a new scope declares the label in the same pull request, and the test of the contract tells the author to add the scope to the workflow.
- **One source, one test.** The workflow cannot read the label file without a checkout and a YAML tool on the runner. The list in the workflow repeats the label names, and a test in `tests/invariants/test_workflow_contracts.py` parses both files and compares them. The scope `main` is the one scope that the workflow allows with no label: release-please makes that title.
- **Declare scopes that recur.** A scope used twice or more in the evidence names an area of the project. A scope used once is left out. The author picks a declared scope. The check lists the choices.
- **Keep `scope/agent`.** Six items hold it. Titles use `agents`, so both labels exist. The owner can rename the label and its items later.

## Rejected alternatives

- **Declare all 33 undeclared scopes.** It adds labels for one-off words such as `core`, `floor` and `hardening`, and it does not stop the next unknown scope.
- **A test that reads the git history.** It depends on the clone: a shallow clone or a missing `origin/main` changes the result. docs/TESTING.md asks for tests that depend on no host.
- **A test over the titles of GitHub.** It needs the network, and the floor of the tests refuses it.
- **`ignoreLabels` for the release pull request.** It skips the whole check for that pull request. Listing `main` skips nothing else.
- **Read the label file in the workflow with `yq`.** It needs a checkout step and a tool that the runner may not have, and nothing can test it offline. The repeated list has a test.
