# 03 — Seed the plugin into the image

Resolves the spike's original problem and the remaining half of F9. Depends on
`02`.

## Goal

Every container built from `agent-desktop` starts with the same pinned
`agentdev` plugin available to Claude Code and Codex — no clone, no network, no
firewall allowlist entry, and no per-repository configuration. A project used as
an external devcontainer gets the skills and their Codex presentation metadata
whether or not it carries this repository's `.claude/settings.json`,
`.agents/plugins/marketplace.json`, or `postCreateCommand`.

The plugin tree under `.agents/plugins/agentdev/` remains the only source of
truth. The image must not create a Claude-only or Codex-only copy that can drift
from it.

## Mechanism

Claude Code and Codex consume one pinned plugin directory through different
metadata and bootstrap mechanisms. Stage it once:

```text
/opt/agentdev-plugin-seed/
  .claude-plugin/marketplace.json
  .agents/plugins/marketplace.json
  .agents/plugins/agentdev/
    .claude-plugin/plugin.json
    .codex-plugin/plugin.json
    agents/
    skills/
    hooks/
    bin/
```

Both marketplace files resolve `.agents/plugins/agentdev/`; that directory is
the single immutable plugin payload in the image. Do not create separate Claude
and Codex plugin trees. Product-managed indexes and caches may be separate, but
they are derived state, not independently authored or staged plugin copies.

### Claude Code seed

`CLAUDE_CODE_PLUGIN_SEED_DIR` points at a directory mirroring
`~/.claude/plugins`:

```text
$CLAUDE_CODE_PLUGIN_SEED_DIR/
  known_marketplaces.json
  marketplaces/<name>/...
  cache/<marketplace>/<plugin>/<version>/...
```

At startup Claude Code registers the seeded marketplaces into its primary
configuration and uses the seeded caches in place. This works both interactively
and under `-p`.

Populate it during the image build by pointing `CLAUDE_CODE_PLUGIN_CACHE_DIR` at
the target. Add the marketplace from the shared staged root, not from a GitHub
URL, so the build makes no network request and the installed files derive from
the same plugin directory Codex receives:

```bash
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed \
  claude plugin marketplace add /opt/agentdev-plugin-seed
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed \
  claude plugin install agentdev@agent-devcontainer
```

### Codex registration from the shared seed

Codex supports packaged plugins through `.codex-plugin/plugin.json` and local
marketplaces through `.agents/plugins/marketplace.json`. Do not copy loose
skills into `~/.codex/skills`; that drops the plugin identity, marketplace
policy, install-surface metadata, and any future bundled capabilities.

The staged Codex `marketplace.json` resolves the same plugin directory with the
relative local source `./.agents/plugins/agentdev`. At container startup,
register the shared root as a local marketplace and install its plugin into the
active `CODEX_HOME` (which defaults to `~/.codex`):

```bash
codex plugin marketplace add /opt/agentdev-plugin-seed
codex plugin add agentdev@agent-devcontainer
```

Put this bootstrap in the image entrypoint, not this repository's
`scripts/devcontainer-postCreateCommand.sh`. External consumers do not inherit
that script. The entrypoint runs after Docker has mounted any persistent
`/root/.codex` volume, so Codex writes its configuration and mutable installed
cache to the mounted state while the shared immutable plugin directory stays
visible under `/opt/agentdev-plugin-seed`.

The bootstrap must be idempotent and version-aware. It may add the marketplace,
hydrate a missing cache, or refresh an older seeded version, but it must preserve
unrelated Codex configuration, authentication, and an explicit user-disabled
state. Starting an already-current container must not rewrite `config.toml`.

## Prerequisites

- Spec `02` merged and a plugin version published.
- A Codex CLI version with the `codex plugin marketplace` and
  `codex plugin add` commands; fail the image build with a useful message if the
  installed CLI does not provide them.
- `install_agentic_tools: true`, which the desktop image already sets.

## Implementation

### 1. Extend the `agentic_tools` role

The seeds belong in `ansible/roles/agentic_tools`, which already owns the Claude
Code and Codex installs. Add role-prefixed defaults equivalent to:

```yaml
agentic_tools_seed_plugins: false
agentic_tools_plugin_source_root: ''
agentic_tools_plugin_marketplace: agent-devcontainer
agentic_tools_plugin_name: agentdev
agentic_tools_plugin_version: ''
agentic_tools_plugin_seed_root: /opt/agentdev-plugin-seed
agentic_tools_claude_plugin_seed_dir: /opt/claude-seed
```

Keep the capability disabled by default, consistent with the other optional
image capabilities. `docker/desktop/agent-desktop.Dockerfile` enables it and
passes `/provision` as the source root and the image build argument as the
version while the read-only build-context mount exists.

The role must remain independently runnable. Guard the seed tasks on
`agentic_tools_seed_plugins` and assert their own prerequisites; do not depend
on a `register:` produced by another role.

### 2. Pin and cross-check one version

The build must seed the exact catalog snapshot from its build context, not
whatever a remote branch contains at build time. `AGENTDEV_PLUGIN_VERSION`
defaults to the current release and is passed to the role as
`agentic_tools_plugin_version`.

Before staging the plugin or generating product-specific state, assert that
this value equals all authoritative package metadata:

- `.agents/plugins/agentdev/.claude-plugin/plugin.json` `version`;
- `.agents/plugins/agentdev/.codex-plugin/plugin.json` `version`; and
- `.claude-plugin/marketplace.json`'s `agentdev` entry `version`.

Expose the checked value in the image:

```dockerfile
LABEL org.opencontainers.image.version.agentdev="${AGENTDEV_PLUGIN_VERSION}"
```

A mismatch is a build failure, not a warning. Extend Renovate's custom manager
from `02` to bump the build argument along with the release metadata.

### 3. Stage one shared plugin directory

Copy the two marketplace files and the canonical
`.agents/plugins/agentdev/` tree into `agentic_tools_plugin_seed_root`, retaining
the repository-relative layout shown under Mechanism. Copy the plugin payload
once. Both marketplace entries must point to that same directory; neither may
point at a product-specific copy.

Preserve all files under the plugin root, including both plugin manifests,
scripts, references, hooks, assets, and per-skill metadata. Do not reconstruct
the package from selected `SKILL.md` files.

### 4. Seed Claude Code

Create Claude Code's required seed index and cache from
`agentic_tools_plugin_seed_root`; do not stage another source plugin tree for
Claude. Then export `CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed` in the image
environment. Do not put the variable in `devcontainer.json`: a consumer that
writes its own configuration against the published image must inherit it
without knowing the seed exists.

### 5. Register and activate the same plugin in Codex (F9)

Add a small bootstrap helper owned by the role and call it from
`docker/desktop/entrypoint.sh` before `exec "$@"`. The helper must:

1. return successfully when seeding is disabled or Codex is not installed;
2. create the active `CODEX_HOME` when needed without replacing it;
3. register the staged marketplace by local absolute path;
4. install or refresh `agentdev@agent-devcontainer` only when the installed
   copy is absent or its manifest version differs from the seed manifest;
5. preserve an explicit disabled state and every unrelated marketplace/plugin;
6. fail loudly when a requested initial install is corrupt, while avoiding a
   container-start failure solely because an already-installed user cache is
   unreadable; and
7. make no network request.

Remove the repository-specific Codex install commands from
`scripts/devcontainer-postCreateCommand.sh` after the entrypoint owns this
responsibility. Keeping both paths would hide image-seed regressions in this
repository while external consumers still fail.

### 6. Complete and ship Codex metadata

The shared plugin is more than the skill bodies. Treat these three Codex-facing
metadata layers as part of the release contract:

1. **Plugin manifest** — `.codex-plugin/plugin.json` carries `name`, `version`,
   `description`, publisher fields, `skills: "./skills/"`, and `interface`
   metadata. Keep the existing display name, short and long descriptions,
   developer name, category, capabilities, website, and up to three starter
   prompts aligned with the actual catalog.
2. **Marketplace entry** — `.agents/plugins/marketplace.json` carries the
   marketplace display name plus the `agentdev` local source, category, and
   explicit `policy.installation` and `policy.authentication`. Use
   `INSTALLED_BY_DEFAULT` for the image-provided catalog and `ON_INSTALL` for
   authentication; the plugin currently needs no external authentication.
3. **Skill UI metadata** — every user-facing skill listed in the plugin README
   has `skills/<skill>/agents/openai.yaml` with `interface.display_name`, a
   25–64 character `short_description`, and a one-sentence `default_prompt`
   that names `$<skill-name>`. Keep this outside `SKILL.md` frontmatter.

Do not add icons, colors, screenshots, legal URLs, MCP dependencies, or policy
fields without a real requirement and corresponding asset or destination. Copy
all metadata into the shared plugin directory from the canonical plugin tree;
never generate a second image-only manifest or plugin payload.

Extend `validate_agent_files` where necessary so validation fails when:

- the Claude and Codex plugin versions or Claude marketplace version diverge;
- the Claude and Codex marketplace sources do not normalize to the same staged
  plugin directory;
- a README-listed skill lacks `agents/openai.yaml` or its default prompt names
  a different skill; or
- required Codex plugin/marketplace interface fields are missing or malformed.

### 7. Make immutable sources and mutable state explicit

Claude Code never writes to its seed and disables auto-update for seeded
marketplaces. The shared plugin source must also remain immutable; only
product-managed indexes plus Codex's registered configuration and installed
cache under `CODEX_HOME` are mutable. Install the shared source and Claude seed
root-owned and mode `0755`, and document in the role README that updating the
plugin means rebuilding the image.

The persistent `agentdev-codex` volume mounted at `/root/.codex` shadows files
baked directly into that directory. This design avoids the collision by keeping
the shared source at `/opt/agentdev-plugin-seed` and hydrating the mounted volume
from the entrypoint. Do not remove `skills/` from the volume or place image files
under `/root/.codex`; that would split Codex state across two ownership models.

For Claude Code, document that a seeded marketplace wins when a repository
declares the same marketplace. A developer who needs a different version must
disable the seeded plugin before enabling another source. For Codex, document
the equivalent plugin disable/alternate-marketplace flow and ensure the
entrypoint preserves that explicit disabled state.

### 8. Update the READMEs

The repository's "Using it in another project" documentation and the
`agentic_tools` role README must state:

- the image includes one plugin directory with both Claude Code and Codex
  metadata;
- no project settings or post-create hook are needed for the image-provided
  version;
- Claude Code invokes skills as `/agentdev:<skill>` and Codex selects them as
  `$agentdev:<skill>` when qualified by the plugin; and
- changing the bundled version requires an image rebuild, while an explicitly
  disabled plugin stays disabled.

## Acceptance criteria

- A container from the built image, opened on an unrelated project with no
  `.claude/`, `.codex/`, or `.agents/` configuration, lists the `agentdev`
  catalog in both Claude Code and Codex.
- Codex shows the plugin's display metadata and every README-listed skill's
  `display_name`, `short_description`, and starter prompt from
  `agents/openai.yaml`.
- No network request is made to resolve either catalog at session start.
  Verified with `ENABLE_FIREWALL=true` and no marketplace host in the allowlist.
- The Claude seed, Codex plugin manifest, and image label report the same version
  as `AGENTDEV_PLUGIN_VERSION`.
- Re-running the entrypoint against an already-current `CODEX_HOME` leaves
  `config.toml` byte-for-byte unchanged.
- A pre-existing unrelated Codex marketplace/plugin remains configured, and a
  user-disabled `agentdev` plugin remains disabled after container restart.
- `install_agentic_tools: false` still produces a working image with neither
  seed nor bootstrap side effect.
- The `agentdev-claude` and `agentdev-codex` volumes do not shadow either
  immutable seed.
- The staged Claude and Codex marketplace entries resolve to the same
  `/opt/agentdev-plugin-seed/.agents/plugins/agentdev` directory.

## Test plan

- Validate the catalog and its Codex metadata:

  ```bash
  uv run validate_agent_files --recommend . --require-marketplace claude codex
  uv run pytest py_packages
  ```

- Validate Ansible changes:

  ```bash
  (cd ansible && uv run ansible-lint .)
  (cd ansible && uv run ansible-playbook --syntax-check playbooks/setup-dev.yml)
  ```

- Build the local image per the README, then verify Claude Code from a scratch
  project:

  ```bash
  docker run --rm local/agent-desktop bash -lc '
    test "$CLAUDE_CODE_PLUGIN_SEED_DIR" = /opt/claude-seed &&
    claude -p "list your available agentdev skills" | grep agentdev'
  ```

- Verify Codex with an empty persistent state directory, inspect the installed
  manifest and marketplace JSON, and run the container a second time against
  the same state to prove idempotence. Also repeat with an unrelated marketplace
  configured and with `agentdev` explicitly disabled.
- Start the devcontainer with `ENABLE_FIREWALL=true` and no marketplace host in
  `.devcontainer/firewall-allowlist.txt`; confirm both catalogs still load.
- Open a scratch project as an external devcontainer against the image and
  confirm discovery on both agents with no project-level configuration or
  lifecycle script.
- Build once with `install_agentic_tools: false` and confirm the image is valid
  and seed-free.

## Notes

The real image gate is a local build, per the repository README. Catalog,
Ansible, and syntax validation passing is necessary but not sufficient for this
spec.
