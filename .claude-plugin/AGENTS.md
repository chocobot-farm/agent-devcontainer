# Claude marketplace publisher instructions

This directory publishes the catalog developed under `.agents/plugins/agentdev/`.

- Validate changes with
  `uv run validate_agent_files --recommend . --require-marketplace claude codex`.
- Keep the marketplace entry version aligned with both the Claude and Codex plugin
  manifests.
- `.claude/settings.json` is this repository's own strict-JSON Claude configuration; do not
  add comments or trailing commas to it.
- This repository enables the plugin from the marketplace declared here through its own
  `.claude/settings.json`.
