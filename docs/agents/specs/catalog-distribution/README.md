# Catalog distribution — spike findings

Investigation into how this repository's shared assets should reach other
projects, and how improvements made here migrate outward without turning every
consumer into a diverging copy.

Supersedes finding **F8** of Dr.QP's
[`agent-devcontainer-migration`](https://github.com/Dr-QP/Dr.QP/pull/452) spike,
which concluded that sharing the `.claude` catalog across repositories had "no
mechanism that does not hurt". Three of the mechanisms it needed have since
shipped.

**Status:** spike complete and fully implemented. Specs `01` (F8), `02` (F5, F6,
F9), and `03` (F4, the container half of F9) have all landed. Spec `03`'s
plugin-seed mechanism was subsequently replaced by a staged catalog plus a
`postCreate` install — see F4 for the two container-shape constraints that forced
it, and F9 for why that change closed the Codex half at the same time.

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
| Bake the catalog into the image?               | **Yes — staged, then installed by a lifecycle hook.** Not seeded (F4).  |
| Distribute `.github/` workflows and actions?   | **No.** Out of scope by decision; they stay repository-local.           |
| Template-sync the remaining scaffolding files? | **No.** Four files is below the threshold where Copier pays for itself. |

## The three layers

Distribution failed as a single problem because it is three problems with
different churn rates and different natural mechanisms.

| Layer               | Contents                                                                                                         | Churn  | Mechanism                                                                   |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------- |
| 1. Environment      | `ansible/`, `docker/`, the published image                                                                       | Low    | GHCR image pinned by digest                                                 |
| 2. Agent catalog    | `.agents/plugins/agentdev/skills`, `.agents/plugins/agentdev/agents`, hooks, `.agents/plugins/agentdev/bin/*.sh` | High   | Plugin + marketplace, staged in the image and installed at container create |
| 3. Repo scaffolding | `.devcontainer/`, `AGENTS.md`, `.claude/settings.json`                                                           | Medium | Manual copy (see F7)                                                        |

## How the catalog reaches a container

The delivered mechanism, after spec `03`'s plugin seed was built and then
replaced (F4). One catalog, one marketplace name, two agents, no
per-repository configuration:

```text
image build      /opt/agentdev/                     staged copy: root-owned, read-only,
  (ansible)        .claude-plugin/marketplace.json  outside $HOME so no volume shadows it
                   .agents/plugins/marketplace.json
                   .agents/plugins/agentdev/…

postCreate       reinstall-agentdev-codex.sh  "$AGENTDEV_CATALOG_DIR"
  (once)         reinstall-agentdev-claude.sh "$AGENTDEV_CATALOG_DIR" user
                 → both agents resolve agentdev@agent-devcontainer to /opt/agentdev

postStart        reinstall-agentdev-codex.sh        no argument → this checkout
  (every start)  reinstall-agentdev-claude.sh       → both agents flip to the workspace
```

Three properties follow, and together they are why this replaced the seed:

- **The image never installs anything.** It only stages files. Both agents record
  installed plugins under `~/.claude` and `~/.codex`, which are mounted as
  external named volumes, so anything installed at build time is shadowed for
  every container after the first (F4).
- **The workspace wins when it has something to say.** The same two scripts take
  a catalog root as their first argument. `postStart` passes none, so a
  repository that ships the catalog re-registers its own copy over the image's on
  every container start — the development-mode override the seed could not
  provide. In a project that ships no marketplace the scripts find no manifest
  and exit quietly, leaving the image install standing.
- **Both agents are treated identically.** Claude Code and Codex each have a
  marketplace manifest and a plugin CLI; the two scripts differ only in which
  binary they call and in Claude's installation scope (F9).

Verified against a local image build: `/opt/agentdev` staged clean, both CLIs
reporting `agentdev@agent-devcontainer` 3.0.0 installed and enabled with
`--network none`, and the `postStart` pass flipping both from `/opt/agentdev` to
the workspace with no duplicate marketplace left behind.

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

Inside the `agent-desktop` image this composes with the container install rather
than competing with it: that install is an ordinary user-scope
`claude plugin install`, so a project declaration resolves the usual way. The
seed this replaced did not behave that way — it overrode a declaration of the
same name and had to be disabled first (F4).

### F4 — Plugin seeds exist for this case, and we deliberately do not use them (priority: none, resolved)

`CLAUDE_CODE_PLUGIN_SEED_DIR` points at a build-time-populated directory
mirroring `~/.claude/plugins` (`known_marketplaces.json`, `marketplaces/<name>/`,
`cache/<marketplace>/<plugin>/<version>/`). At startup Claude Code registers the
seeded marketplaces and uses the seeded caches in place, with no clone. Spec `03`
built exactly that.

**It was then replaced.** Two container-shape constraints, both discovered by
building it, rule out every build-time mechanism — including the one that reads
as the obvious improvement, installing the plugin during the image build:

- **A seeded marketplace unconditionally overwrites the same-named entry** in
  `known_marketplaces.json` at every session start. A repository that develops the
  catalog in its own workspace can never win against a seed of the same name; the
  frozen build-time copy always loads. The only escape was an opt-out env var,
  which is a workaround rather than a design.
- **`~/.claude` and `~/.codex` are mounted as external named volumes**
  (`.devcontainer/docker-compose.yml`), and both agents record marketplaces,
  enablement, and plugin caches under exactly those paths. Docker copies image
  content into a named volume only when the volume is empty, so a build-time
  `claude plugin install` is correct on a clean machine and **silently inert**
  for every container thereafter. This is why the install cannot simply move
  deeper into the image.

What replaced it: the image **stages** the catalog at `/opt/agentdev` — a
verbatim copy of `.claude-plugin/` and `.agents/`, root-owned and read-only,
outside `$HOME` so no volume shadows it — and the `postCreate` hook installs from
that path through each agent's own plugin CLI, after the volumes are mounted.
Nothing is special-cased and nothing is frozen; `postStart` re-registers the
workspace copy on top, which is the development-mode override the seed made
impossible.

The catalog is staged from the build context rather than cloned from a published
release, which spec `03` had assumed. That keeps the image and the catalog it
carries on the same commit, keeps the build offline, and does not depend on a
release existing. `AGENTDEV_PLUGIN_VERSION` therefore pins by assertion — both
the Claude marketplace manifest and the plugin's Codex manifest must declare
exactly that version or the build fails — rather than by selecting what to fetch,
and Renovate does not manage it: it is this repository's own version, bumped by
hand alongside the manifests at release.

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

None of the four needs editing after the copy. That is deliberate: an earlier
design required a consumer to delete two `containerEnv` entries this repository
sets to `""`, and a copy that kept them would have silently got no catalog with
no error to explain why. The current mechanism (F4) removes the setting
altogether — the `postStart` scripts detect whether the workspace ships a
marketplace of its own and act accordingly, so template and consumer run the
same configuration.

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

### F9 — Codex has its own plugin system now (priority: medium, resolved)

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
| Install CLI          | `claude plugin marketplace add` / `install`                     | `codex plugin marketplace add` / `add`                              |
| Build-time seed      | `CLAUDE_CODE_PLUGIN_SEED_DIR` — exists, unused (F4)             | **none**                                                            |

The in-repository half is therefore fully resolved, and by a better mechanism
than re-pointing a symlink: `.devcontainer/scripts/reinstall-agentdev-codex.sh`
registers a catalog root as a local Codex marketplace and installs the plugin,
mirroring the Claude script exactly.

**The container half is resolved too, and by the same mechanism** — which is the
outcome that made spec `03`'s seed worth abandoning. Codex has no seed equivalent
(no `CODEX_*_SEED_DIR`), and its registry, enablement flags, and plugin cache all
live under `$CODEX_HOME`, the path the `agentdev-codex` volume mounts over. Once
F4 stopped trying to install anything at build time, that stopped mattering: both
scripts take a catalog root as their first argument, `postCreate` passes the
staged `/opt/agentdev`, and `postStart` passes nothing so the workspace copy wins.
The asymmetry between the two agents disappears with it.

Spec `03`'s workaround — seeding `<seed>/codex/skills` and symlinking
`$CODEX_HOME/skills` at it — is gone, along with the three weaknesses it carried:
it shipped skills but not the plugin's `agents/`, it was invisible to
`codex plugin list`, and it depended on a lifecycle script re-creating a symlink
after every volume mount.

### F10 — Private marketplaces have a flaky background auto-update (priority: low)

The background refresh disables git credential helpers for its `git pull`, so it
cannot authenticate to a private repository over HTTPS. It falls back to a full
re-clone, which uses stored credentials but can time out. SSH remotes are
unaffected.

`plume-works/agent-devcontainer` is public, so this does not bite today. It
constrains any future decision to make it private.

## Costs summary

| Cost                                                           | Severity |
| -------------------------------------------------------------- | -------- |
| Rewriting 37 catalog path references (F6, done)                | High     |
| Permanent skill namespacing (F5)                               | Medium   |
| Teaching `validate_agent_files` the plugin layout (F9, done)   | Medium   |
| Building the seed before discarding it for a staged copy (F4)  | Medium   |
| Catalog changes need an image rebuild to reach containers (F4) | Low      |
| Four scaffolding files copied by hand (F7)                     | Low      |

## Benefits summary

- The catalog has exactly one source of truth, consumed by version rather than
  by copy. This is the whole point.
- Every container gets the catalog with no clone, no network, no firewall
  allowlist entry, and no per-repository configuration (F4) — in full for both
  Claude Code and Codex, through each agent's own plugin CLI (F9).
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
   spec file removed. Its plugin-seed mechanism was later replaced by a staged
   catalog plus a `postCreate` install, which also closed the Codex half of F9
   (see F4).

F7 is a decision, not a task: no spec.
