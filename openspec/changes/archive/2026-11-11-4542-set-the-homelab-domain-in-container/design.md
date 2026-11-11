# Design

## Decisions
- **Only a Deployment, only `env[].value`.** The start page is a Deployment, and its two variables are literal `env[].value` fields. A value from `valueFrom` holds no text to replace. A StatefulSet, a DaemonSet or a CronJob gets the same field when a manifest needs it.
- **Only a value that holds the placeholder.** `_host_fields` returns an environment value only when `holds_template_domain_value` is true. The Argo CD gate reads the same pointers as the allowed places of the placeholder. If `_host_fields` returned each value, the gate would allow the placeholder in no more places, but the list would no longer say which values deploy-stack changes.
- **Init containers before containers.** The pointers come in the order of the fields in the pod spec of the API, so a patch reads in the same order as `kubectl get -o yaml`.
- **Test, then replace.** Each value gets a `test` operation before its `replace`, as each host does. A value that git moves or changes in its object then fails the manifest generation of the Application, and does not put the domain into another variable.

## Rejected alternatives
- **Kustomize `replacements`.** It copies one field or one delimited segment of a field from a source object. It cannot replace the domain inside `$(MY_POD_IP):3000,start.example.com`, and the source object would have to hold the real domain in git.
- **A ConfigMap that deploy-stack writes, read by `envFrom`.** It adds an object that no Application owns, for each Application that needs the domain. The patch builder already covers this through the Application.
- **Each environment value of every workload kind.** No manifest needs more than a Deployment now. A wider scan changes more objects with no test against a real need.
