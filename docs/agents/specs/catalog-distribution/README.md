# Catalog distribution — spike findings

Investigation into how this repository's shared assets should reach other
projects, and how improvements made here migrate outward without turning every
consumer into a diverging copy.

Supersedes finding **F8** of Dr.QP's
[`agent-devcontainer-migration`](https://github.com/Dr-QP/Dr.QP/pull/452) spike,
which concluded that sharing the `.claude` catalog across repositories had "no
mechanism that does not hurt". Three of the mechanisms it needed have since
shipped.

**Status:** spike complete; specs `01` (F8), `02` (F5, F6, F9), and `03` (F4, the
container half of F9) have all landed. One gap is open and unspecified: seeding
the catalog into a container for **Codex**, whose own plugin system postdates this
spike — see F9.

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

| Layer               | Contents                                                                                                         | Churn  | Mechanism                        |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------- |
| 1. Environment      | `ansible/`, `docker/`, the published image                                                                       | Low    | GHCR image pinned by digest      |
| 2. Agent catalog    | `.agents/plugins/agentdev/skills`, `.agents/plugins/agentdev/agents`, hooks, `.agents/plugins/agentdev/bin/*.sh` | High   | Claude Code plugin + marketplace |
| 3. Repo scaffolding | `.devcontainer/`, `AGENTS.md`, `.claude/settings.json`                                                           | Medium | Manual copy (see F7)             |

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
the folder is trusted. The file must be strict JSON — no comments, no trailing
commas:

```json
{
  "extraKnownMarketplaces": {
    "agent-devcontainer": {
      "source": {
        "source": "github",
        "repo": "plume-works/agent-devcontainer"
      }
    }
  },
  "enabledPlugins": { "agentdev@agent-devcontainer": true }
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

Resolved by spec `03`: `agentic_tools` seeds the catalog at `/opt/agentdev-seed`
during the image build and the image exports `CLAUDE_CODE_PLUGIN_SEED_DIR`.

It seeds from the build context rather than cloning a published release, which
the spec had assumed. Seeding from the context keeps the image and the catalog it
carries on the same commit, keeps the build offline, and does not depend on a
release existing. `AGENTDEV_PLUGIN_VERSION` therefore pins by assertion — the
manifest must declare exactly that version or the build fails — rather than by
selecting what to fetch, and Renovate does not manage it: it is this
repository's own version, bumped by hand alongside the manifests at release.

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

### F5 — Namespacing is the one irreversible cost (priority: medium, resolved)

Plugin skills are always namespaced. `/pr-merge` becomes `/agentdev:pr-merge`.
There is no opt-out; namespacing is what prevents collisions between plugins.

Mitigation is limited to choosing a short plugin name. `agentdev` was chosen, and
spec `02` landed the rename: every skill now resolves as `/agentdev:<name>`.
Personal and project skills of the same name continue to resolve unnamespaced,
so a consumer that wants a short alias can still shadow one locally.

### F6 — 37 hardcoded catalog paths must move to `${CLAUDE_SKILL_DIR}` (priority: high, resolved)

Skill bodies and their scripts invoke each other by literal repository-relative
path. Under a plugin the catalog lives in `~/.claude/plugins/cache/...`, and
every one of these breaks.

| File                                                            | Refs |
| --------------------------------------------------------------- | ---- |
| `skills/remote-codespace-session/SKILL.md`                      | 7    |
| `skills/extract-github-actions-logs/SKILL.md`                   | 5    |
| `skills/pr-open/SKILL.md`                                       | 3    |
| `skills/pr-open/scripts/review-git-changes.sh`                  | 3    |
| `skills/remote-codespace-session/scripts/codespace-ensure.sh`   | 3    |
| `skills/remote-codespace-session/scripts/codespace-teardown.sh` | 3    |
| `skills/git-merge-resolve/SKILL.md`                             | 2    |
| `skills/git-merge-resolve/scripts/git-merge-resolve.sh`         | 2    |
| `skills/pr-review/SKILL.md`                                     | 2    |
| `skills/pr-open/scripts/push-branch.sh`                         | 2    |
| `skills/update-branch/scripts/update-branch.sh`                 | 2    |
| `skills/create-skill/SKILL.md`                                  | 1    |
| `skills/remote-codespace-session/scripts/codespace-sync.sh`     | 1    |
| `skills/update-branch/SKILL.md`                                 | 1    |

14 files, 37 references. Mechanical, but it was the bulk of spec `02`. Resolved
there: self-references became `${CLAUDE_SKILL_DIR}/...`, cross-references became
namespaced skill invocations, and `validate_agent_files` now fails on any literal
catalog path reintroduced inside the plugin.

The `Bash(.claude/skills/*/scripts/*)` entry in
[`.claude/settings.json`](../../../../.claude/settings.json) had the same
problem. Spec `02` replaced it with per-skill `allowed-tools` frontmatter plus
permission rules that match the plugin cache path, because the Bash tool rejects
a command string containing an unexpanded `${...}` and so never sees the
substituted form.

### F7 — Scaffolding residue is four files, below the Copier threshold (priority: low)

With `.github/` excluded by decision and the general `scripts/*.sh` absorbed by
the plugin (F2), what a consuming repository still copies is:

`.devcontainer/devcontainer.json`, `.devcontainer/docker-compose.yml`,
`AGENTS.md`, `.claude/settings.json`.

#### Two of those settings are wrong in a copy

`.devcontainer/devcontainer.json` sets both of these to the empty string in
`containerEnv`, and **a project templated from this repository must delete both
entries** so they are inherited from the image again:

| Variable                      | Set by                                  | Consumed by                                                                  |
| ----------------------------- | --------------------------------------- | ---------------------------------------------------------------------------- |
| `CLAUDE_CODE_PLUGIN_SEED_DIR` | the image (`/opt/agentdev-seed/claude`) | Claude Code, to register the seeded marketplace at session start (F4)        |
| `AGENTDEV_SEED_DIR`           | the image (`/opt/agentdev-seed`)        | `link-codex-seed-skills.sh`, to relink `$CODEX_HOME/skills` after mount (F9) |

The blanking is correct here and only here: this repository _is_ the catalog's
source, and a seeded marketplace overwrites the same-named entry at every session
start — so leaving it on would mean editing the catalog in the workspace while
both agents kept loading the frozen build-time copy. A consumer has the opposite
need, and a copy that keeps the blanks silently gets no catalog at all, with no
error to explain why. This is the one setting where inheriting the template's
value is a bug rather than a default.

Copier (`.copier-answers.yml` + `copier update`) is the only mainstream tool
designed to replay upstream template changes onto a copy that has diverged, via
a three-way merge. It is the right answer at scale and the wrong answer at four
files: the `.jinja` suffixing, the answers file, and the added dependency cost
more than the copying they replace.

Revisit if consumer count grows past a handful, or if these four files start
churning.

### F8 — Nothing rebuilds a consumer when the base image moves (priority: high, resolved)

Carried forward unchanged from the Dr.QP spike's F7. A consumer pinned to
`agent-desktop` went stale silently. Resolved by spec `01`: both GHCR images
are now pinned by tag-plus-digest, and `.github/renovate.json` bumps them as a
single grouped pull request. Spec `02` added the `customManager` for the plugin `version`
pin a consumer declares in `enabledPlugins`.

### F9 — Codex has its own plugin system now; only its seeding is unsolved (priority: medium, partly resolved)

As originally written, this finding said Codex does not understand Claude
plugins: `.codex/skills` was a symlink to `../.claude/skills`, `.codex/agents/*.md`
were generated trampolines validated by `validate_agent_files`, and moving the
canonical catalog into a plugin directory broke both.

**That premise no longer holds.** Codex shipped a plugin system of its own —
marketplaces and plugins, `codex plugin marketplace add` and `codex plugin add`
(verified on `codex-cli` 0.146.0). The catalog is now packaged for both agents
from the same tree, and neither the symlink nor the trampolines exist: `.codex/`
holds only a README and `setup-codex-cloud.sh`.

|                      | Claude Code                                                     | Codex                                                               |
| -------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------- |
| Plugin manifest      | `.agents/plugins/agentdev/.claude-plugin/plugin.json`           | `.agents/plugins/agentdev/.codex-plugin/plugin.json`                |
| Marketplace manifest | `.claude-plugin/marketplace.json`                               | `.agents/plugins/marketplace.json`                                  |
| Registered state     | `known_marketplaces.json` + `enabledPlugins` in `settings.json` | `[marketplaces.*]` / `[plugins."*@*"]` in `$CODEX_HOME/config.toml` |
| Plugin cache         | `~/.claude/plugins/cache/<mkt>/<plugin>/<version>`              | `$CODEX_HOME/plugins/cache/<mkt>/<plugin>`                          |
| Build-time seed      | `CLAUDE_CODE_PLUGIN_SEED_DIR` (F4)                              | **none**                                                            |

The in-repository half is therefore fully resolved, and by a better mechanism
than re-pointing a symlink: `.devcontainer/scripts/reinstall-agentdev-codex.sh`
registers this checkout as a local Codex marketplace at `postCreate`, the same
way the Claude half installs from `.claude-plugin/marketplace.json`.

**The container half is not.** Codex has no seed equivalent — no
`CODEX_*_SEED_DIR`, and its marketplace registry, enablement flags, and plugin
cache all live under `$CODEX_HOME`, which is exactly the path the `agentdev-codex`
volume mounts over. There is no out-of-home location to point it at, so
build-time plugin state cannot survive a container start the way the Claude seed
does.

Spec `03` predates the Codex plugin system and worked around it: it seeds
`<seed>/codex/skills` outside `$HOME` and symlinks `$CODEX_HOME/skills` at it,
restoring the link from `postCreate` after the volume mounts
(`link-codex-seed-skills.sh`). This was never specified, and it is weaker than
the Claude seed in three ways:

- **Skills only.** The plugin's `agents/` do not travel; a seeded container gets
  no `agentdev` agents in Codex.
- **Invisible to Codex's own tooling.** The skills arrive as personal skills, so
  `codex plugin list` does not show the catalog and there is no per-project
  equivalent of `/plugin disable`.
- **Load-bearing symlink.** Correctness depends on a lifecycle script re-running
  after every volume mount, rather than on state the agent resolves itself.

Closing this properly needs its own spec. The obvious candidate — run
`codex plugin marketplace add` against a staged catalog at build time, as the
Claude half already does — founders on the `$CODEX_HOME` shadowing above; the
alternative is relocating `CODEX_HOME` out of `$HOME` entirely, which trades the
problem for a persistence question about `auth.json`.

### F10 — Private marketplaces have a flaky background auto-update (priority: low)

The background refresh disables git credential helpers for its `git pull`, so it
cannot authenticate to a private repository over HTTPS. It falls back to a full
re-clone, which uses stored credentials but can time out. SSH remotes are
unaffected.

`plume-works/agent-devcontainer` is public, so this does not bite today. It
constrains any future decision to make it private.

## Costs summary

| Cost                                                         | Severity |
| ------------------------------------------------------------ | -------- |
| Rewriting 37 catalog path references (F6, done)              | High     |
| Permanent skill namespacing (F5)                             | Medium   |
| Teaching `validate_agent_files` the plugin layout (F9, done) | Medium   |
| Codex containers get seeded skills but no seeded plugin (F9) | Medium   |
| Catalog changes need an image rebuild to reach seeds (F4)    | Low      |
| Four scaffolding files copied by hand (F7)                   | Low      |

## Benefits summary

- The catalog has exactly one source of truth, consumed by version rather than
  by copy. This is the whole point.
- Every container gets the catalog with no clone, no network, no firewall
  allowlist entry, and no per-repository configuration (F4) — in full for Claude
  Code, skills-only for Codex until F9's remaining half is specified.
- Codespaces, cloud sessions, and routines are covered for the first time (F3).
- A consuming project's `.claude/` shrinks to a settings block.
- The general/project-specific boundary in `scripts/` is forced to become
  explicit rather than drifting (F2).

## Implementation order

1. `01-base-image-version-pinning.md` — resolved F8. **Landed**; spec file
   removed.
2. `02-claude-catalog-plugin.md` — resolved F5, F6, and the in-repository half
   of F9. **Landed**; spec file removed.
3. `03-plugin-seed-in-image.md` — resolved the original problem. **Landed**;
   spec file removed.
4. _Unwritten_ — seed the Codex plugin, not just its skills (F9). Blocked on
   deciding what happens to `$CODEX_HOME` state under the `agentdev-codex`
   volume; until then the skills symlink stands in.

F7 is a decision, not a task: no spec.
