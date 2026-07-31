# agent-devcontainer

A general-purpose, Ansible-provisioned development container built for
agent-driven development. Python + Node, Docker-in-Docker, an Xpra remote
desktop, Claude Code and Codex preinstalled, an opt-in egress firewall, and a
curated catalog of agents and skills.

Nothing in here is project-specific — point your repo at the published image, or
copy the template in and go.

## What's in the image

| Area          | Contents                                                                                  |
| ------------- | ----------------------------------------------------------------------------------------- |
| Python        | `uv` (installer, resolver, venv manager), system `python3`, `pre-commit`                  |
| JavaScript    | `bun` (also used to install global CLIs), Node.js 24 from NodeSource, `yarn`              |
| Agents        | `@anthropic-ai/claude-code`, `@openai/codex`, `@modelcontextprotocol/inspector`           |
| Build tooling | `build-essential`, CMake (Kitware), Ninja, `pkg-config`                                   |
| Lint / CI     | `shellcheck`, `zizmor` (pinned + checksummed), `jq`, `ffmpeg`, `btop`                     |
| Git / GitHub  | `git`, `git-lfs`, `gh` + a transparent auth wrapper that injects `GH_TOKEN` from the host |
| Shells        | `bash` and `fish` (with fisher + bass), UTC timezone, `en_US.UTF-8` locale                |
| Desktop       | Xpra 6.4.3 with the HTML5 client, xpra-html5 v19, VirtualGL 3.1.4, mesa, Xvfb             |
| Containers    | Docker CE + CLI + buildx + compose (daemon started by the devcontainer DinD feature)      |
| Secrets       | GNOME Keyring Secret Service, brought up headless so `gh auth login` can persist a token  |
| Firewall      | `init-firewall.sh` + a NOPASSWD sudoers entry — **installed but inert unless enabled**    |

Images are published multi-arch (`linux/amd64` + `linux/arm64`), built on native
runners and merged into a single manifest:

- `ghcr.io/chocobot-farm/agent-desktop:edge` — the development image
- `ghcr.io/chocobot-farm/ubuntu-ansible:edge` — the Ansible base it is built from

## Using it in another project

### Option 1 — point an existing devcontainer at the image

```jsonc
// .devcontainer/devcontainer.json
{
  "image": "ghcr.io/chocobot-farm/agent-desktop:edge@sha256:fd10e509373a3ba461f323b4f15b053c468e59c907ef5d8f4be02966fb400a74",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:4.0.0": {},
  },
  "containerEnv": {
    "DEV_WORKSPACE_FOLDER": "/workspaces/${localWorkspaceFolderBasename}",
  },
}
```

`DEV_WORKSPACE_FOLDER` is the one variable the image cares about: the `gh`
wrapper PATH shim and the firewall allowlist lookup both read it, falling back to
the `workspace_folder` baked in at build time.

### Option 2 — copy the template

Copy `.devcontainer/` and `scripts/` into your repo, and enable the `agentdev`
plugin (see [The agent catalog](#the-agent-catalog)) instead of copying the
catalog. The compose file already wires up the shared agent-auth volumes, the MCP
gateway sidecar, and worktree-safe mounts. Adjust `workspaceFolder` and the
`agentdev-*` volume names if you want per-project isolation.

### Staying on the current image

Both options pin `agent-desktop` by tag **and** digest
(`:edge@sha256:...`) rather than a bare moving tag, so the image a consumer runs
never changes silently under it. That only helps if something advances the pin
when the image is rebuilt — point [Renovate](https://docs.renovatebot.com/) (or
an equivalent) at the repository with a config that includes the `docker` (or
`docker-compose`/`dockerfile`, depending on where the pin lives) manager, for
example:

```jsonc
// renovate.json
{
  "extends": ["config:recommended"],
}
```

This repository's own [`.github/renovate.json`](.github/renovate.json) is the
reference implementation, including how it groups the `agent-desktop` and
`ubuntu-ansible` digest bumps into a single pull request.

## Enabling the firewall

The firewall is installed in the image but does nothing until you ask for it.
Set `ENABLE_FIREWALL=true` and edit the allowlist:

```jsonc
// .devcontainer/devcontainer.json
"containerEnv": { "ENABLE_FIREWALL": "true" }
```

`.devcontainer/firewall-allowlist.txt` is read at container start, so per-branch
edits take effect on the next start with no image rebuild. It default-DROPs IPv4
egress, blocks IPv6 entirely, preserves Docker's embedded-DNS NAT rules, and
self-verifies (a known-blocked host must fail, `api.github.com` must succeed) —
exiting non-zero if either check goes the wrong way.

## Reaching the Xpra desktop

`scripts/devcontainer-postStartCommand.sh` starts Xpra in the background on
display `:100`. The HTML5 client port is derived per devcontainer as
`14500 + cksum(DEVCONTAINER_ID) % 100`, so parallel worktrees never collide;
`forwardPorts` covers the whole `14500-14599` range. Open the forwarded port in a
browser. For GPU-accelerated rendering, prefix the app with `vglrun`.

Manage it directly with `/start-xpra.sh --background`, `--stop`, or
`--port <n>`.

## Provisioning knobs

`docker/desktop/agent-desktop.Dockerfile` enables all four capability roles. To
build a leaner image, flip them off — they default to `false` in
`ansible/playbooks/group_vars/all.yml`:

| Variable                        | Effect when `true`                                                      |
| ------------------------------- | ----------------------------------------------------------------------- |
| `install_xpra`                  | Xpra + xpra-html5 + VirtualGL + mesa/Xvfb (the largest single addition) |
| `install_docker`                | Docker CE, CLI, buildx, compose (installed, daemon not started)         |
| `install_agentic_tools`         | Claude Code, Codex, MCP inspector                                       |
| `install_devcontainer_firewall` | `init-firewall.sh` + sudoers entry (still runtime-gated)                |
| `setup_user`                    | Create a non-root `devuser` (1001:1001) instead of running as root      |
| `workspace_folder`              | Fallback workspace path baked into the image                            |

## Building locally

The desktop image's build context is the repository root — the dockerfile
bind-mounts the whole context at `/provision` so Ansible can read both `ansible/`
and `docker/bin/gh`.

```bash
docker build -t local/ubuntu-ansible docker/ansible

docker buildx build \
  -f docker/desktop/agent-desktop.Dockerfile \
  --build-arg FROM_IMAGE=local/ubuntu-ansible \
  -t local/agent-desktop .
```

Then smoke it:

```bash
docker run --rm local/agent-desktop bash -lc '
  bun --version && node --version && uv --version &&
  gh --version | head -1 && cmake --version | head -1 && zizmor --version &&
  command -v xpra init-firewall.sh gnome-keyring-daemon'
```

Ansible alone, without a build:

```bash
cd ansible
uv run ansible-lint .
uv run ansible-playbook --syntax-check playbooks/setup-dev.yml
```

## The agent catalog

The catalog ships as the `agentdev` Claude Code and Codex plugin in [`plugin/`](plugin/) —
four agents (Principal Engineer plus the TDD Red/Green/Refactor trio) and 21
skills covering git, pull requests, review, CI log extraction, formatting, and
container/Codespace escalation. **[plugin/README.md](plugin/README.md) documents
what it contains and how to enable it in another repository**; the rest of this
section is about developing it here.

### Source of truth

`plugin/` is canonical. Everything else is derived:

| Path                               | Role                                                          |
| ---------------------------------- | ------------------------------------------------------------- |
| `plugin/`                          | Canonical agents, skills, hooks, and `bin/` scripts.          |
| `plugin/.claude-plugin/`           | Packages the catalog for Claude Code.                         |
| `plugin/.codex-plugin/`            | Packages the same catalog for Codex.                          |
| `.claude-plugin/marketplace.json`  | Publishes the plugin so other repositories can consume it.    |
| `.agents/plugins/marketplace.json` | Publishes the repo-local Codex marketplace entry.             |
| `.claude/settings.json`            | This repository enabling its own plugin from the marketplace. |

### Editing rules

- **Edit files under `plugin/`, never under `.codex/`.**
- Codex consumes agents and skills directly from the canonical plugin tree; do
  not recreate `.codex/agents/` trampolines or a `.codex/skills` symlink.
- Use the [create-agent](plugin/skills/create-agent/SKILL.md) and
  [create-skill](plugin/skills/create-skill/SKILL.md) skills — they encode the
  frontmatter, discovery-description, and validation rules.
- **Never write a repository-relative catalog path** such as
  `.claude/skills/<name>/...`: inside a plugin it resolves nowhere. Use
  `${CLAUDE_SKILL_DIR}/...` for a path within the same skill, and a namespaced
  invocation for a sibling skill.
- A script in `plugin/bin/` must not assume it sits inside the repository it
  operates on. Resolve the target repository from the working directory (see
  [`plugin/bin/__utils.sh`](plugin/bin/__utils.sh)).
- Bump `version` in both plugin manifests and the marketplace entry together.

[AGENTS.md](AGENTS.md) has the repository conventions agents follow.

### Iterating and validating

```bash
claude --plugin-dir ./plugin   # override the installed copy for a session
claude plugin validate ./plugin
```

CI enforces the last two commands; run them before pushing a catalog change:

```bash
uv sync --all-groups
uv run validate_agent_files --recommend plugin
uv run pytest py_packages
```

## Repository layout

```
.devcontainer/   devcontainer.json, compose (devcontainer + mcp-gateway), init, firewall allowlist
docker/
  ansible/       ubuntu-ansible base image
  desktop/       agent-desktop image, entrypoint, Xpra launcher
  bin/gh         transparent gh auth wrapper baked onto PATH
ansible/         inventories + setup-dev.yml + 18 roles
scripts/         devcontainer lifecycle hooks and repository plumbing
plugin/          the agentdev plugin: agents, skills, hooks, bin/  (canonical)
  .claude-plugin/  Claude Code package manifest
  .codex-plugin/   Codex package manifest
.claude-plugin/  marketplace manifest publishing the plugin
.agents/plugins/ repo-local Codex marketplace and canonical-plugin symlink
.claude/         this repository's own settings.json
.codex/          repository-specific Codex setup
py_packages/     validate_agent_files — the agent-catalog validator
.github/         composite docker actions + CI, reformat, and validation workflows
```

## License

MIT — see [LICENSE](LICENSE).
