# 03 — Seed the plugin into the image

Resolves the spike's original problem. Depends on `02`.

## Goal

Every container built from `agent-desktop` starts with the `agentdev` catalog
already available — no clone, no network, no firewall allowlist entry, and no
per-repository configuration. A project used as an external devcontainer gets
the skills whether or not it opts in via `.claude/settings.json`.

## Mechanism

`CLAUDE_CODE_PLUGIN_SEED_DIR` points at a directory mirroring `~/.claude/plugins`:

```
$CLAUDE_CODE_PLUGIN_SEED_DIR/
  known_marketplaces.json
  marketplaces/<name>/...
  cache/<marketplace>/<plugin>/<version>/...
```

At startup Claude Code registers the seeded marketplaces into its primary
configuration and uses the seeded caches in place. This works both interactively
and under `-p`.

Populate it during the image build by pointing `CLAUDE_CODE_PLUGIN_CACHE_DIR` at
the target, which installs directly there and skips a copy step:

```bash
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed \
  claude plugin marketplace add plume-works/agent-devcontainer
CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-seed \
  claude plugin install agentdev@plume-works
```

## Prerequisites

- Spec `02` merged and a plugin version published.
- `install_agentic_tools: true`, which the desktop image already sets.

## Implementation

### 1. Extend the `agentic_tools` role

The seed belongs in `ansible/roles/agentic_tools`, which already owns
the Claude Code and Codex installs. Add to `defaults/main.yml`, prefixed per the
repository's role-variable convention:

```yaml
agentic_tools_seed_plugins: false
agentic_tools_plugin_marketplace: plume-works/agent-devcontainer
agentic_tools_plugin_name: agentdev@plume-works
agentic_tools_plugin_seed_dir: /opt/claude-seed
```

Default `false`, consistent with every other capability flag in
`group_vars/all.yml`, and enabled explicitly by
`docker/desktop/agent-desktop.Dockerfile`.

The role must remain independently runnable: guard the tasks on the Claude Code
binary being present rather than on a `register:` from an earlier role.

### 2. Pin the seeded version

The build must install a specific plugin version, not whatever `main` holds at
build time. An unpinned seed makes the image non-reproducible and defeats spec
`01`'s entire premise.

Take the version from a build argument defaulting to the current release, and
surface it in the image so it is inspectable:

```
LABEL org.opencontainers.image.version.agentdev="${AGENTDEV_PLUGIN_VERSION}"
```

Renovate's custom manager from `02` bumps the same value.

### 3. Export the runtime variable

Set `CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-seed` in the image environment, not
in `devcontainer.json`. A consumer that writes its own `devcontainer.json`
against the published image must inherit the seed without knowing it exists —
that is the whole point of this spec.

### 4. Make the seed read-only, deliberately

Claude Code never writes to the seed and disables auto-update for seeded
marketplaces. Make that explicit in the filesystem: install the tree
root-owned and mode `0755`, and document in the role README that updating the
catalog means rebuilding the image.

The escape hatch for a developer who needs a newer catalog than the image
carries is `extraKnownMarketplaces` in the project's `.claude/settings.json` —
but note the composition rule works the other way: if a declared marketplace
already exists in the seed, Claude uses the seed copy. Overriding a seeded
version requires `/plugin disable` on the seeded plugin first. Document this;
it is the least obvious behaviour in this spec.

### 5. Seed the Codex catalog too (F9)

Codex has no plugin mechanism. In the same role, place the catalog at
`~/.codex/skills` so Codex sessions in the container see it. Source it from the
same pinned checkout used for the plugin install, so the two cannot drift.

Note the interaction with `.devcontainer/docker-compose.yml`: `agentdev-codex`
is mounted at `/root/.codex` as a shared external volume, which shadows anything
the image places there. Either seed to a path outside the volume and symlink
from `scripts/devcontainer-postCreateCommand.sh`, or exclude `skills/` from the
volume. Resolve this before implementing — the same shadowing applies to
`agentdev-claude` at `/root/.claude`, which is precisely why the seed lives at
`/opt/claude-seed` and not under `$HOME`.

### 6. Update the README

The "Using it in another project" section should state that the catalog ships
with the image, what the namespaced invocation looks like, and how to pin a
different version.

## Acceptance criteria

- A container from the built image, opened on an unrelated project with no
  `.claude/` configuration at all, lists the `agentdev` skills and can invoke
  `/agentdev:pr-open`.
- No network request is made to resolve the catalog at session start. Verified
  with `ENABLE_FIREWALL=true` and no allowlist entry for the marketplace.
- The seeded plugin version matches the build argument and the image label.
- `install_agentic_tools: false` still produces a working image with no seed.
- The `agentdev-codex` volume does not shadow the seeded Codex catalog.

## Test plan

- `(cd ansible && uv run ansible-lint .)` and
  `(cd ansible && uv run ansible-playbook --syntax-check playbooks/setup-dev.yml)`.
- Local image build per the README, then:

  ```bash
  docker run --rm ghcr.io/plume-works/agent-desktop:local bash -lc '
    echo "$CLAUDE_CODE_PLUGIN_SEED_DIR" &&
    ls "$CLAUDE_CODE_PLUGIN_SEED_DIR/marketplaces" &&
    claude -p "list your available skills" | grep agentdev'
  ```

- Start the devcontainer with `ENABLE_FIREWALL=true` and no marketplace host in
  `.devcontainer/firewall-allowlist.txt`; confirm the catalog still loads.
- Open a scratch project as an external devcontainer against the image and
  confirm skill discovery with no project-level `.claude/`.
- Build once with `install_agentic_tools: false` and confirm the image is valid
  and seed-free.

## Notes

The real image gate is a local build, per the repository README. Ansible lint
and syntax-check passing is necessary but not sufficient for this spec.
