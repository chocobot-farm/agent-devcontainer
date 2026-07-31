# `agentdev` — the shared agent catalog, as a Claude Code plugin

This directory is the **single source of truth** for the agent catalog. It is a
Claude Code plugin, published by
[`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) at the
repository root, so other projects consume it by version instead of by copy.

| Path                         | Purpose                                                          |
| ---------------------------- | ---------------------------------------------------------------- |
| `.claude-plugin/plugin.json` | The plugin manifest: name and version.                           |
| `agents/`                    | Agent specs, one `*.agent.md` per agent. Canonical.              |
| `skills/`                    | Skills, one `<name>/SKILL.md` per skill (+ optional `scripts/`). |
| `hooks/hooks.json`           | Claude Code lifecycle hooks, plus the scripts they run.          |
| `bin/`                       | General-purpose scripts; on `PATH` while the plugin is enabled.  |

## Consuming it

Add to the consuming repository's `.claude/settings.json`:

```jsonc
{
  "extraKnownMarketplaces": {
    "chocobot-farm": {
      "source": {
        "source": "github",
        "repo": "chocobot-farm/agent-devcontainer",
      },
    },
  },
  "enabledPlugins": { "agentdev@chocobot-farm": true },
}
```

Skills are namespaced by the plugin name: `/agentdev:open-pr`,
`/agentdev:pr-merge`, and so on. There is no opt-out — namespacing is what keeps
plugins from colliding.

## Editing rules

- **Edit files here, never in `.codex/`.** `.codex/skills` is a symlink to
  `plugin/skills`, and `.codex/agents/*.md` are thin trampolines that delegate to
  the canonical `plugin/agents/*.agent.md`.
- When you add, rename, or re-describe an agent, update its `.codex/agents/`
  trampoline so `name` and `description` match exactly. CI enforces this through
  `validate_agent_files`.
- Use the [create-agent](skills/create-agent/SKILL.md) and
  [create-skill](skills/create-skill/SKILL.md) skills — they encode the
  frontmatter, discovery-description, and validation rules.
- **Never write a repository-relative catalog path** such as
  `.claude/skills/<name>/...`: inside a plugin it resolves nowhere. Use
  `${CLAUDE_SKILL_DIR}/...` for a path within the same skill, and a namespaced
  invocation for a sibling skill. `validate_agent_files` fails on the literal.
- A script in `bin/` must not assume it sits inside the repository it operates
  on. Resolve the target repository from the working directory (see
  [`bin/__utils.sh`](bin/__utils.sh)).
- Bump `version` in both `plugin.json` and the marketplace entry together;
  `validate_agent_files` fails when they disagree.

## Iterating and validating

```bash
claude --plugin-dir ./plugin          # override the installed copy for a session
claude plugin validate ./plugin
uv run validate_agent_files --recommend plugin
uv run pytest py_packages/validate_agent_files/tests
```
