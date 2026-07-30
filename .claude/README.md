# `.claude/` — canonical AI tooling source of truth

This directory is the **single source of truth** for the repository's agent
configuration. Everything else is generated from it or symlinked to it.

| Path            | Purpose                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| `agents/`       | Agent specs, one `*.agent.md` per agent. Canonical.                     |
| `skills/`       | Skills, one `<name>/SKILL.md` per skill (+ optional `scripts/`).         |
| `hooks/`        | Claude Code lifecycle hooks wired up from `settings.json`.               |
| `settings.json` | Permissions, additional directories, hooks, enabled plugins.             |

## Editing rules

- **Edit files here, never in `.codex/`.** `.codex/skills` is a symlink to
  `.claude/skills`, and `.codex/agents/*.md` are thin trampolines that delegate
  to the canonical `.claude/agents/*.agent.md`.
- When you add, rename, or re-describe an agent, update its `.codex/agents/`
  trampoline so `name` and `description` match exactly. CI enforces this through
  `validate_agent_files`.
- Use the [create-agent](skills/create-agent/SKILL.md) and
  [create-skill](skills/create-skill/SKILL.md) skills — they encode the
  frontmatter, discovery-description, and validation rules.

## Local overrides

`*.local.json` is gitignored, so `settings.local.json` can hold machine-specific
permissions without touching the shared configuration.

## Validation

```bash
uv run validate_agent_files --recommend .claude
uv run pytest py_packages/validate_agent_files/tests
```

The same check runs as a pre-commit hook and in the `validate-agent-files`
workflow.
