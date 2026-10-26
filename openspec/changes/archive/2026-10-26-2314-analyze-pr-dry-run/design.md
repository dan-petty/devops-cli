# Design

The dry-run check sits right after the `--explain` branch, before the GitHub session is created.

## Rejected alternatives

- **Keep the call and skip only the write.** The call to `get_pull` is the external communication that #412 forbids. Rejected.
- **Add a shared decorator.** One command needs the check. A decorator adds code with no second user. Rejected.
