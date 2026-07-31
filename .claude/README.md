# `.claude/` — this repository's own Claude Code configuration

The agent catalog no longer lives here. It ships as the `agentdev` plugin under
[`plugin/`](../plugin/README.md), published by the marketplace manifest in
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json). What
remains in this directory is the configuration a project keeps for itself.

| Path            | Purpose                                                                   |
| --------------- | ------------------------------------------------------------------------- |
| `settings.json` | Permissions, additional directories, known marketplaces, enabled plugins. |

`settings.json` must be strict JSON: no comments and no trailing commas. Claude
Code rejects the file outright if it does not parse, which silently drops every
permission and the plugin registration with it.

This repository consumes its own plugin, which is the only way the consumer path
stays tested: `settings.json` registers the `chocobot-farm` marketplace and
enables `agentdev@chocobot-farm`. Skills therefore resolve namespaced, as
`/agentdev:open-pr` and so on.

## Local overrides

`*.local.json` is gitignored, so `settings.local.json` can hold machine-specific
permissions without touching the shared configuration.

## Iterating on the catalog

Point Claude Code at the working tree instead of the installed copy:

```bash
claude --plugin-dir ./plugin
```

## Validation

```bash
claude plugin validate ./plugin
uv run validate_agent_files --recommend plugin
uv run pytest py_packages/validate_agent_files/tests
```

The same check runs as a pre-commit hook and in the `validate-agent-files`
workflow.
