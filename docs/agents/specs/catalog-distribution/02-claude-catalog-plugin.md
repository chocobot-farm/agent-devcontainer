# 02 — Convert the `.claude` catalog to a plugin

Resolves **F5**, **F6**, **F9**. Depends on `01`. This is the bulk of the work —
budget one to two days.

## Goal

Turn this repository's agent catalog into a Claude Code plugin, distributed by a
marketplace hosted in the same repository, so that any project can consume it by
version instead of by copy.

## Target layout

The repository becomes its own marketplace. The plugin lives in a top-level
`plugin/` directory so `.claude/` remains free for this repository's own
project-level configuration.

```
.claude-plugin/
  marketplace.json          # the catalog of one plugin
plugin/
  .claude-plugin/
    plugin.json             # name: agentdev, version: x.y.z
  skills/                   # moved from .claude/skills
  agents/                   # moved from .claude/agents
  hooks/
    hooks.json              # moved from .claude/settings.json "hooks"
  bin/                      # general scripts, on PATH when enabled
.claude/
  settings.json             # permissions + extraKnownMarketplaces + enabledPlugins
```

`.claude-plugin/` holds only manifests. Every component directory sits at the
plugin root, never inside `.claude-plugin/`.

### `marketplace.json`

```jsonc
{
  "name": "chocobot",
  "plugins": [
    {
      "name": "agentdev",
      "source": "./plugin",
      "description": "General-purpose agent catalog: git, pull requests, review, CI, formatting, container and Codespace escalation.",
      "version": "1.0.0",
    },
  ],
}
```

Set an explicit `version` and bump it per release. Omitting it makes every
commit a new version, which is the wrong trade for a catalog that receives
work-in-progress commits.

## Naming

The plugin is named `agentdev`. Skills become `/agentdev:pr-merge`,
`/agentdev:open-pr`, and so on (**F5**). This is permanent and has no opt-out;
the short name is the only available mitigation.

## Implementation

### 1. Split `scripts/` before moving anything

Decide, per script, whether it is general or repository plumbing. With `.github/`
excluded from sharing by decision, plugin `bin/` is the only route by which shell
tooling reaches another project, so this split determines what a consumer needs
beyond the image and the plugin.

| Script                                            | Destination                          |
| ------------------------------------------------- | ------------------------------------ |
| `python-lint-check.sh`                            | plugin `bin/`                        |
| `super-linter-local.sh`                           | plugin `bin/`                        |
| `super-linter-env.sh`, `super-linter-defaults.sh` | plugin `bin/` (sourced by the above) |
| `shellcheck-fix.sh`                               | plugin `bin/`                        |
| `__utils.sh`                                      | plugin `bin/` (sourced)              |
| `validate-super-linter-tool-versions.sh`          | stays — CI plumbing                  |
| `devcontainer-*.sh`                               | image — lifecycle hooks              |
| `uv-sync.sh`                                      | stays — project-specific             |

A script moved to `bin/` must not assume a repository-relative location. Audit
each for `$(dirname "$0")`-relative reads outside its own directory.

### 2. Move the catalog

`git mv .claude/skills plugin/skills` and `git mv .claude/agents plugin/agents`.
Preserve history; the review of step 3 is much easier against a rename than
against a delete-plus-add.

Move the `hooks` object out of `.claude/settings.json` into
`plugin/hooks/hooks.json`. The schema is identical. Note that
`session-start.sh` references `$CLAUDE_PROJECT_DIR`, which under a plugin points
at the consuming project, not at the plugin — which is what that hook wants, so
it is correct as written. Verify rather than assume.

### 3. Rewrite the 37 hardcoded paths (F6)

Every literal `.claude/skills/<name>/...` in a skill body or script becomes
`${CLAUDE_SKILL_DIR}/...`, which expands to the directory containing that
skill's `SKILL.md` regardless of working directory. The 14 affected files are
enumerated in the
[findings](README.md#f6--37-hardcoded-catalog-paths-must-move-to-claude_skill_dir-priority-high-blocks-02).

Two categories need different handling:

- **Self-references** — a skill invoking its own script. Straight substitution.
- **Cross-references** — `open-pr/SKILL.md` pointing at `update-branch`, and the
  prose links in `pr-review/SKILL.md` and `create-skill/SKILL.md`. These become
  skill invocations by namespaced name (`/agentdev:update-branch`), not paths.
  A plugin skill cannot reach a sibling's directory by relative path.

Also update the cross-skill references in the `description` frontmatter, which
name sibling skills in prose ("Commit creation belongs to `git-commit`"), and
the four `/.claude/...` links in `AGENTS.md`.

### 4. Move the permission rule

`Bash(.claude/skills/*/scripts/*)` in `.claude/settings.json` cannot match the
plugin cache path. Replace it with per-skill `allowed-tools` frontmatter using
the same `${CLAUDE_SKILL_DIR}` substitution, so each rule matches exactly the
command its own body tells Claude to run:

```yaml
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/*)
```

Only the seven skills that ship scripts need this.

### 5. Re-point the Codex side (F9)

`.codex/skills` currently symlinks `../.claude/skills`. Re-point it at
`../plugin/skills`. Codex does not understand plugins; it consumes the directory
directly, which the chosen layout keeps possible.

The `.codex/agents/*.md` trampolines must continue to match their canonical
agents in `plugin/agents/`. CI enforces this.

### 6. Teach `validate_agent_files` the plugin layout

`py_packages/validate_agent_files` walks `.claude` today — it is invoked as
`uv run validate_agent_files --recommend .claude`. It needs to accept the plugin
root, and it should additionally validate:

- `plugin.json` and `marketplace.json` parse, and the `version` fields agree.
- No skill body contains a literal `.claude/skills/` path — a regression guard
  for step 3, and the cheapest possible protection against reintroducing F6.
- Trampoline parity against `plugin/agents/`, as before.

Update the invocation in `.github/workflows/validate-agent-files.yml` and the
`AGENTS.md` instruction that documents the command.

### 7. Dogfood it here

Add to this repository's own `.claude/settings.json`:

```jsonc
{
  "extraKnownMarketplaces": {
    "chocobot": {
      "source": {
        "source": "github",
        "repo": "chocobot-farm/agent-devcontainer",
      },
    },
  },
  "enabledPlugins": { "agentdev@chocobot": true },
}
```

This repository consuming its own plugin is the only way the consumer path stays
tested. Iterate on the catalog with `claude --plugin-dir ./plugin`, which
overrides the installed copy for that session.

### 8. Add the Renovate custom manager

Spec `01` deferred the `extraKnownMarketplaces` version rule until the plugin
existed. Add it now, so consumers are told when the catalog moves.

## Acceptance criteria

- `claude plugin validate ./plugin` prints `✔ Validation passed`.
- Every skill and agent loads under the `agentdev` namespace; `/context` lists
  the four agents.
- No file under `plugin/` contains a literal `.claude/skills/` path.
- The seven script-bearing skills run their scripts without a permission prompt.
- `uv run validate_agent_files --recommend` passes against the new layout, and
  fails when a literal catalog path is reintroduced.
- `.codex/skills` resolves, and trampoline parity holds in CI.
- A scratch repository containing only the settings block from step 7 can invoke
  `/agentdev:open-pr` end to end.

## Test plan

- `claude plugin validate ./plugin`, and `--strict` to surface warnings.
- `claude --plugin-dir ./plugin`, then invoke each of the seven script-bearing
  skills and confirm `${CLAUDE_SKILL_DIR}` resolved correctly.
- `uv run pytest py_packages` for the validator changes, including a new
  regression test for the literal-path guard.
- `uv run validate_agent_files --recommend` on the converted tree.
- `scripts/super-linter-local.sh` for the full formatting and lint gate.
- Install from the marketplace in a scratch repository and confirm the plugin
  resolves from GitHub rather than from a local path.

## Risks

- **Namespacing is irreversible** (F5). Confirm the ergonomics are acceptable
  before starting, not after the rename lands.
- **Cross-skill references are not a mechanical substitution** (step 3). They
  are the most likely place for a silent break, because a wrong path in prose
  fails at agent runtime rather than at validation time. The step 6 guard covers
  literal paths but not a wrong namespaced name.
- **Codex parity is a hard CI gate** (F9), not a follow-up. A conversion that
  leaves `.codex` broken cannot merge.
