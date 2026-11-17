# Design

## Decisions
- Drop `SEARXNG_IMAGE` and not read the image from the live Deployment: the constant only named the image in the success message, and the check tests the running service whatever image it runs. Reading the Deployment would add a `kubectl` call for a line of text.
- The table tests compare chart names: `{chart for chart, _ in pinned_charts()}` against the table keys. `pinned_charts()` stays, because the deploy-stack version test reads it.
- `test_the_dead_engines_file_gives_a_date_and_a_reason` keeps the format check of the file and drops the comparison with the engine names of the image.
- The SearXNG note of Renovate keeps the steps that a person can still do: read the notes of the release and run `devops k8s searxng-check`.

## Rejected alternatives
- Keep the version keys and let Renovate bump them with a custom manager: the owner rejected checks of manifest values (#6060).
- Read the engine names from the image in a test: it needs the image and a network pull in the test run, and it still checks a manifest value.
