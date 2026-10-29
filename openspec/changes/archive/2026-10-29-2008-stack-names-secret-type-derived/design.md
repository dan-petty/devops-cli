# Design

## Stack names

`config/constants.py` holds three names:

- `CONST_K8S_STACKS`: `infra`, `llm`, `logging`, `devops` and `gitea`, in deploy order. This is the one place that names a stack.
- `CONST_K8S_ALL_STACKS`: `all`.
- `CONST_K8S_VALID_STACKS`: `(*CONST_K8S_STACKS, CONST_K8S_ALL_STACKS)`.

`_resolve_stacks` returns `list(CONST_K8S_STACKS)` for `all` and `[stack]` for a name in `CONST_K8S_STACKS`. The help texts are f-strings over the same constants. deploy-stack is registered with `help=HELP.k8s.deploy_stack`, as push-secrets is, so its summary comes from the catalog.

Rejected:

- The tuple in `networking.py`, as the issue proposes. `networking.py` imports `HELP` from `devops_cli.lang`, and the help texts need the tuple. A tuple in `networking.py` makes an import cycle. #2157 moved the tuple to `constants.py` for that reason.
- `all` in the deploy order tuple, with `_resolve_stacks` removing it again. Then every reader must know that one value is a selector and not a stack. Two names make the difference clear.

## Derived entries

```python
DerivedSource(
    "postgres://{user}:{password}@<host>:5432/<db>",
    {"user": LiteralSource("<user>"), "password": KeyringSource("<key>")},
)
```

- `template` is a `str.format` template. Each field names one input. The value of each input is quoted with `urllib.parse.quote(value, safe="")` before it fills its field.
- An input is a `KeyringSource`, a `SettingSource` or a `LiteralSource`. An input is not a derived source.
- `plan_push` resolves every entry that is not derived, for every Secret, in table order. It then resolves the derived entries. Thus a derived entry sees each value that the push adopts or generates for an input (`_Sources.plan_store`), whatever the order of the entries and of the rows.
- An input with no value makes the derived entry missing when it is required, and skipped when it is optional. The message names the input and the `devops config set` command of a managed option.
- A derived value is compared with the live value as any other value is: `created`, `unchanged`, `rotated`, or `differs` when `--rotate` is not given.
- A derived value is never adopted, generated or stored in the keyring. It has no `store_key`, and the dry run lists no keyring write for it.
- The source label is `derived from <input labels>`. `--plan`, the push output and the dry run's placeholder use it. No label holds a value.
- The dry run lists the keyring reads of the derived inputs after the reads of every other entry, in the order that `plan_push` makes them.
- `keyring_only_keys` also counts the keyring inputs of a derived entry.

Rejected:

- Inputs that name other keys of the same Secret. The hooks of #1392 and #1393 are in the keyring and are not keys of their Secrets, so such inputs could not build them.
- A derived value that replaces a differing live value without `--rotate`. The push help says that a live value is never replaced without `--rotate`, and a derived value can hold a credential.
- `string.Template` instead of `str.format`. Both are in the standard library. The other help texts and messages of the project use `str.format` fields.

## Secret type

`ClusterSecret.secret_type` is a `Literal` of the types the table uses: `Opaque` (the default) and `kubernetes.io/basic-auth`. A row that needs another built-in type adds it to the `Literal`. `_secret_manifest` writes the row's type, so the push and the dry run carry it.

Rejected:

- A free `str`. Kubernetes accepts any non-empty type as a custom type, so a typo such as `kubernetes.io/basic_auth` would go to the cluster without an error. A `Literal` lets mypy find it.
