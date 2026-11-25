### Friction

`devops scan trivy|sast|secrets` with `--format json` or `yaml` prints only the findings. A scan that gave no result (`not installed`, `failed`, `not_applicable`) prints `[]`, which reads as a clean scan. The MCP tools give this output for `output_format: json`, so an agent reads a missing scanner as "no findings".

### What should happen

The JSON and YAML output holds the status and the reason of the scan next to the findings. A scan that gave no result never prints only `[]`.

### Evidence

- Found during #1435 on 2026-10-24. #1435 made the table output report a scan with no result as not run (`CONST_SCAN_NO_RESULT_STATUSES`), but the JSON and YAML output still print only the findings.


Source: https://github.com/dan-petty/devops-cli/issues/1435
