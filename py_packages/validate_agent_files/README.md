# validate_agent_files

CLI tools for validating skills, agent files, and prompt files.

## Installation

```bash
pip install -e .
```

## Usage

```bash
validate_agent_files                     # Validate skills, agents, and prompts under .
validate_agent_files plugin              # Validate the agentdev plugin catalog
validate_agent_files plugin/skills plugin/agents   # Validate multiple paths
validate_agent_files --kind skills       # Validate only skill files
validate_agent_files --kind agents       # Validate only agent files
validate_agent_files --kind prompts      # Validate only prompt files
validate_agent_files --recommend         # Show recommendations
validate_agent_files --ci                # CI mode (nonzero exit on errors)
```

## Notes

- `skills-ref` is a required dependency and the primary validator for skill files.
- Local validation still checks repository-specific rules such as duplicate skill names,
  cross-references, agent handoffs, and prompt `#file:` references.
- When a validated path sits inside a Claude Code plugin, the plugin manifest and its
  marketplace entry must parse and agree on `version`, and no skill body may contain a
  literal repository-relative catalog path (`.claude/skills/...`), which does not resolve
  from a plugin cache.
