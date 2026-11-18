# Design

## Decisions

### Target as the scope

`service`, `runner` and `mcp-server` name the image and stay stable across workflows. A workflow
name would collide because `release.yml` builds all three.

### `mode=max` on each write

The default `min` exports only the final stage and leaves `runner-deps` and `service-deps` out.
The release jobs set `mode=max` already; the change keeps it and makes it a rule.

### Check in the `test-tree` row

#6060 bars a pytest test from asserting a value of a manifest or config file, and `config_reads.toml`
only lowers its counts. The `test-tree` row is the project's offline check of committed files, so a
new module there reads the three workflows and names the file and line of each entry that lacks a
scope. The issue's proposed `tests/invariants` location would fail that gate.

### Pull-request builds read and write no cache

#4646 removed the `cache-to` entry of the pull-request jobs. The change leaves that removal in place
and sets the scope on each `cache-from` entry only.

## Rejected alternatives

- **Default `buildkit` scope:** each write replaces the index of the other images.
- **Workflow name as the scope:** one workflow builds three images, so the scopes collide.
- **`mode=min`:** it leaves the dependency stages out of the export.
- **A pytest test in `tests/invariants`:** #6060 counts and forbids a test that asserts a workflow
  value.
- **A registry cache:** the pull-request jobs have `contents: read` and cannot write one.
