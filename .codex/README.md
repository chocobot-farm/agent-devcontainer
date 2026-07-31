# `.codex/` — Codex repository configuration

The shared agent catalog lives entirely in [`plugin/`](../plugin/) and is
packaged for Codex by
[`plugin/.codex-plugin/plugin.json`](../plugin/.codex-plugin/plugin.json).
Codex discovers the canonical `plugin/agents/` and `plugin/skills/` files
directly, so this directory no longer contains generated trampolines or a
skills symlink.

| Path                   | Nature                                                            |
| ---------------------- | ----------------------------------------------------------------- |
| `setup-codex-cloud.sh` | Codex Cloud bootstrap: ensures `gh` is present and authenticated. |
