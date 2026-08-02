# `.claude/` — this repository's own Claude Code configuration

The agent catalog does not live here; it ships as the `agentdev` plugin under
[`.agents/plugins/agentdev/`](../.agents/plugins/agentdev/README.md). What remains in this directory is the
configuration this repository keeps for itself.

| Path            | Purpose                                                                   |
| --------------- | ------------------------------------------------------------------------- |
| `settings.json` | Permissions, additional directories, known marketplaces, enabled plugins. |

`settings.json` must be strict JSON: no comments and no trailing commas. Claude
Code rejects the file outright if it does not parse, which silently drops every
permission and the plugin registration with it.

This repository consumes its own plugin from the marketplace, which is the only
way the consumer path stays tested.

`*.local.json` is gitignored, so `settings.local.json` can hold machine-specific
permissions without touching the shared configuration.

For editing and validating the catalog itself, see
[The agent catalog](../README.md#the-agent-catalog).
