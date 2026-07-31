# Catalog distribution — spike findings

Investigation into how this repository's shared assets should reach other
projects, and how improvements made here migrate outward without turning every
consumer into a diverging copy.

Supersedes finding **F8** of Dr.QP's
[`agent-devcontainer-migration`](https://github.com/Dr-QP/Dr.QP/pull/452) spike,
which concluded that sharing the `.claude` catalog across repositories had "no
mechanism that does not hurt". Three of the mechanisms it needed have since
shipped.

**Status:** spike complete. Spec `01` (F8) landed; `02` and `03` are written but
not scheduled.

## Problem

`agent-devcontainer` is usable as an external devcontainer from an arbitrary
folder — point another project at the published image and it works. Two things
do not follow:

1. **The agent catalog is invisible inside that container.** Skills and agents
   live in this repository's `.claude/`, which is not the mounted workspace, so
   Claude Code never discovers them.
2. **Bootstrapping a new project by copying this repository** solves discovery
   by duplication, and immediately raises the question this spike exists to
   answer: how does a fix made here reach the copies?

## Verdict

| Question                                       | Answer                                                                  |
| ---------------------------------------------- | ----------------------------------------------------------------------- |
| Distribute the environment?                    | **Solved.** GHCR image, consumed by digest, kept current by Renovate.   |
| Distribute the `.claude` catalog?              | **Yes — convert it to a plugin.** F8's blockers no longer hold.         |
| Bake the catalog into the image?               | **Yes — as a plugin seed,** not as loose files.                         |
| Distribute `.github/` workflows and actions?   | **No.** Out of scope by decision; they stay repository-local.           |
| Template-sync the remaining scaffolding files? | **No.** Four files is below the threshold where Copier pays for itself. |

## The three layers

Distribution failed as a single problem because it is three problems with
different churn rates and different natural mechanisms.

| Layer               | Contents                                                                       | Churn  | Mechanism                        |
| ------------------- | ------------------------------------------------------------------------------ | ------ | -------------------------------- |
| 1. Environment      | `ansible/`, `docker/`, the published image                                     | Low    | GHCR image pinned by digest      |
| 2. Agent catalog    | `.claude/skills`, `.claude/agents`, hooks, `.mcp.json`, general `scripts/*.sh` | High   | Claude Code plugin + marketplace |
| 3. Repo scaffolding | `.devcontainer/`, `AGENTS.md`, `.claude/settings.json`                         | Medium | Manual copy (see F7)             |

## Findings

### F1 — Skill directories may be symlinks (priority: none, resolved)

A `<skill-name>` entry under the enterprise, personal, or project skills
location can be a symlink to a directory elsewhere on disk. Claude Code follows
it, reads `SKILL.md` from the target, and loads the skill once even when the
same target is reachable from more than one location.

F8's framing — "git has no cross-repo symlink" — was true but not the
constraint. The filesystem provides the indirection; git never needed to.

Reference: [Skills — where skills live](https://code.claude.com/docs/en/skills).

### F2 — Plugins now carry the whole catalog, not just skills (priority: none, resolved)

A plugin root may contain `skills/`, `agents/`, `hooks/hooks.json`, `.mcp.json`,
`.lsp.json`, `settings.json`, and `bin/`. Directories in `bin/` are added to the
Bash tool's `PATH` while the plugin is enabled.

This matters more than the skill sharing itself: it means the general half of
`scripts/` (`python-lint-check.sh`, `super-linter-local.sh`, `shellcheck-fix.sh`)
travels with the catalog rather than being copied per repository.

### F3 — A consuming repository opts in with one settings block (priority: none, resolved)

`extraKnownMarketplaces` plus `enabledPlugins` in a repository's
`.claude/settings.json` registers the marketplace and enables the plugin when
the folder is trusted:

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

Repository-declared plugins also install at cloud-session start, so this covers
Codespaces, cloud sessions, and routines — surfaces that neither a personal
`~/.claude/skills` install nor a Docker volume reaches.

### F4 — Plugin seed directories exist for exactly this container case (priority: none, resolved)

`CLAUDE_CODE_PLUGIN_SEED_DIR` points at a build-time-populated directory
mirroring `~/.claude/plugins` (`known_marketplaces.json`, `marketplaces/<name>/`,
`cache/<marketplace>/<plugin>/<version>/`). At startup Claude Code registers the
seeded marketplaces and uses the seeded caches in place, with no clone.

Consequences that make this the right fit here:

- No network at session start, so it works with `ENABLE_FIREWALL=true` and no
  new allowlist entry, and in offline or CI contexts.
- Path resolution probes `$CLAUDE_CODE_PLUGIN_SEED_DIR/marketplaces/<name>/` at
  runtime rather than trusting paths recorded at build time, so the seed
  survives being mounted somewhere other than where it was built.
- Seeds compose with `extraKnownMarketplaces`: a repository that pins a version
  still declares it, and Claude uses the seed copy instead of cloning.
- The seed is read-only. `/plugin marketplace update` and `/plugin marketplace remove`
  against a seeded marketplace fail by design; opting out is `/plugin disable`.

### F5 — Namespacing is the one irreversible cost (priority: medium, accepted)

Plugin skills are always namespaced. `/pr-merge` becomes `/agentdev:pr-merge`.
There is no opt-out; namespacing is what prevents collisions between plugins.

Mitigation is limited to choosing a short plugin name. `agentdev` is proposed.
Personal and project skills of the same name continue to resolve unnamespaced,
so a consumer that wants a short alias can still shadow one locally.

### F6 — 37 hardcoded catalog paths must move to `${CLAUDE_SKILL_DIR}` (priority: high, blocks 02)

Skill bodies and their scripts invoke each other by literal repository-relative
path. Under a plugin the catalog lives in `~/.claude/plugins/cache/...`, and
every one of these breaks.

| File                                                            | Refs |
| --------------------------------------------------------------- | ---- |
| `skills/remote-codespace-session/SKILL.md`                      | 7    |
| `skills/extract-github-actions-logs/SKILL.md`                   | 5    |
| `skills/open-pr/SKILL.md`                                       | 3    |
| `skills/open-pr/scripts/review-git-changes.sh`                  | 3    |
| `skills/remote-codespace-session/scripts/codespace-ensure.sh`   | 3    |
| `skills/remote-codespace-session/scripts/codespace-teardown.sh` | 3    |
| `skills/git-merge-resolve/SKILL.md`                             | 2    |
| `skills/git-merge-resolve/scripts/git-merge-resolve.sh`         | 2    |
| `skills/pr-review/SKILL.md`                                     | 2    |
| `skills/open-pr/scripts/ensure-remote-branch.sh`                | 2    |
| `skills/update-branch/scripts/update-branch.sh`                 | 2    |
| `skills/create-skill/SKILL.md`                                  | 1    |
| `skills/remote-codespace-session/scripts/codespace-sync.sh`     | 1    |
| `skills/update-branch/SKILL.md`                                 | 1    |

14 files, 37 references. Mechanical, but it is the bulk of spec `02`.

The `Bash(.claude/skills/*/scripts/*)` entry in
[`.claude/settings.json`](../../../../.claude/settings.json) has the same
problem and must move to per-skill `allowed-tools` using the same substitution.

### F7 — Scaffolding residue is four files, below the Copier threshold (priority: low)

With `.github/` excluded by decision and the general `scripts/*.sh` absorbed by
the plugin (F2), what a consuming repository still copies is:

`.devcontainer/devcontainer.json`, `.devcontainer/docker-compose.yml`,
`AGENTS.md`, `.claude/settings.json`.

Copier (`.copier-answers.yml` + `copier update`) is the only mainstream tool
designed to replay upstream template changes onto a copy that has diverged, via
a three-way merge. It is the right answer at scale and the wrong answer at four
files: the `.jinja` suffixing, the answers file, and the added dependency cost
more than the copying they replace.

Revisit if consumer count grows past a handful, or if these four files start
churning.

### F8 — Nothing rebuilds a consumer when the base image moves (priority: high, resolved)

Carried forward unchanged from the Dr.QP spike's F7. A consumer pinned to
`agent-desktop` went stale silently. Resolved by spec
[`01`](01-base-image-version-pinning.md): both GHCR images are now pinned by
tag-plus-digest, and `.github/renovate.json` bumps them as a single grouped pull
request. Spec `02` still needs to add a `customManager` there for the plugin
`version` pin it introduces; that section does not exist yet.

### F9 — Codex does not understand Claude plugins (priority: medium)

`.codex/skills` is a symlink to `../.claude/skills`, and `.codex/agents/*.md`
are generated trampolines validated by `validate_agent_files`. Moving the
canonical catalog into a plugin directory breaks both.

The plugin layout must therefore be chosen so the symlink can be re-pointed
within this repository, and the Ansible role that seeds the plugin should also
place the catalog at `~/.codex/skills` for containers. `validate_agent_files`
needs teaching about the new paths — CI enforces trampoline parity, so this is a
hard gate, not a cleanup.

### F10 — Private marketplaces have a flaky background auto-update (priority: low)

The background refresh disables git credential helpers for its `git pull`, so it
cannot authenticate to a private repository over HTTPS. It falls back to a full
re-clone, which uses stored credentials but can time out. SSH remotes are
unaffected.

`chocobot-farm/agent-devcontainer` is public, so this does not bite today. It
constrains any future decision to make it private.

## Costs summary

| Cost                                                      | Severity |
| --------------------------------------------------------- | -------- |
| Rewriting 37 catalog path references (F6)                 | High     |
| Permanent skill namespacing (F5)                          | Medium   |
| Teaching `validate_agent_files` the plugin layout (F9)    | Medium   |
| Catalog changes need an image rebuild to reach seeds (F4) | Low      |
| Four scaffolding files copied by hand (F7)                | Low      |

## Benefits summary

- The catalog has exactly one source of truth, consumed by version rather than
  by copy. This is the whole point.
- Every container gets the catalog with no clone, no network, no firewall
  allowlist entry, and no per-repository configuration (F4).
- Codespaces, cloud sessions, and routines are covered for the first time (F3).
- A consuming project's `.claude/` shrinks to a settings block.
- The general/project-specific boundary in `scripts/` is forced to become
  explicit rather than drifting (F2).

## Implementation order

1. `01-base-image-version-pinning.md` — resolved F8. **Landed**; spec file
   removed.
2. [`02-claude-catalog-plugin.md`](02-claude-catalog-plugin.md) — resolves F5,
   F6, F9. The bulk of the work.
3. [`03-plugin-seed-in-image.md`](03-plugin-seed-in-image.md) — resolves the
   original problem. Depends on `02`.

F7 is a decision, not a task: no spec.
