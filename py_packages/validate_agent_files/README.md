# validate_agent_files

CLI tools for validating skills, agent files, and prompt files.

## Installation

```bash
pip install -e .
```

## Usage

```bash
validate_agent_files                     # Validate skills, agents, and prompts under .
validate_agent_files plugin              # Validate every plugin catalog found below .
validate_agent_files .agents/plugins/agentdev/skills .agents/plugins/agentdev/agents
validate_agent_files --kind skills       # Validate only skill files
validate_agent_files --kind agents       # Validate only agent files
validate_agent_files --kind prompts      # Validate only prompt files
validate_agent_files --recommend         # Show recommendations
validate_agent_files --ci                # CI mode (nonzero exit on errors)
```

## Notes

- `skills-ref` is a required dependency and the primary validator for skill files.
- `plugin` (or `plugins`) is an alias, not a path: it expands to the local plugin sources
  published by the well-known marketplace manifests — `.claude-plugin/marketplace.json` and
  `.agents/plugins/marketplace.json` — so the catalog keeps being validated after it moves,
  and a manifest pointing at a source that has moved away is itself an error. Both source
  forms are understood (`"./path"` and `{"source": "local", "path": "./path"}`), remote
  sources are skipped, a plugin published by both manifests is validated once, and a real
  directory of that name still wins over the alias.
- A requested path that resolves to no catalog — a typo, or a location the catalog has moved
  away from — is an error, so a run that validates nothing can never be mistaken for a pass.
- Local validation still checks repository-specific rules such as duplicate skill names,
  cross-references, agent handoffs, and prompt `#file:` references.
- When a validated path sits inside a Claude Code plugin, the plugin manifest and its
  marketplace entry must parse and agree on `version`, and no skill body may contain a
  literal repository-relative catalog path (`.claude/skills/...`), which does not resolve
  from a plugin cache.
