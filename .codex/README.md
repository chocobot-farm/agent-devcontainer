# `.codex/` — generated Codex view of the agent catalog

**Edit the `.claude/` sources, not this directory.**

| Path                   | Nature                                                                                                                  |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `skills`               | Symlink to `../.claude/skills`. `SKILL.md` follows the open agentskills format, so no translation is needed.            |
| `agents/*.md`          | Trampolines. Each carries the canonical agent's `name`/`description` and delegates to `.claude/agents/<stem>.agent.md`. |
| `setup-codex-cloud.sh` | Codex Cloud bootstrap: ensures `gh` is present and authenticated.                                                       |

A trampoline looks like this in full:

```markdown
---
name: TDD Red
description: <same description as the canonical agent>
---

Read and follow all instructions in `.claude/agents/tdd-red.agent.md`, adapting tool names to the Codex environment.
```

`validate_agent_files` fails the build when a trampoline's `name` or
`description` drifts from its canonical agent, and when a trampoline exists with
no matching agent (or vice versa).
