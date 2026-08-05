# Agentic Tools Role

Installs the agentic CLI tooling used in the workspace and the security layer
that guards it:

- **Bun-managed globals**: `@modelcontextprotocol/inspector`,
  `@anthropic-ai/claude-code`, and `@openai/codex`.
- **[cc-filter](https://github.com/wissem/cc-filter)**: a hard security layer in
  front of Claude Code hooks. It blocks sensitive file access, blocks risky
  shell/search commands, and redacts secrets. The role downloads the
  architecture-appropriate release binary and wires it into the user's Claude
  Code hooks (`~/.claude/settings.json`).
- **The seeded agent catalog** (`agentic_tools_seed_plugins`): a build-time copy
  of a Claude Code plugin marketplace, so every container built from the image
  starts with the catalog already available.

Gated by `install_agentic_tools` in the playbook.

## The catalog seed

`CLAUDE_CODE_PLUGIN_SEED_DIR` points Claude Code at a directory mirroring
`~/.claude/plugins`. At session start it registers the marketplaces it finds
there and uses the seeded plugin cache in place — no clone, no network, no
firewall allowlist entry, and no per-repository configuration:

```text
$agentic_tools_seed_root/
  claude/
    known_marketplaces.json
    marketplaces/<marketplace>/...
    cache/<marketplace>/<plugin>/<version>/...
  codex/
    skills/<skill>/SKILL.md
```

The role builds this by pointing `CLAUDE_CODE_PLUGIN_CACHE_DIR` at the seed and
running `claude plugin marketplace add` and `claude plugin install` against a
copy of the catalog staged inside it, so the CLI owns the layout rather than
this role reproducing it.

Four properties are worth knowing before changing any of it:

- **The catalog is seeded from the provisioning sources**
  (`agentic_tools_seed_source_dir`, the build context under Docker), so the image
  and the catalog it carries always come from the same commit. Set
  `agentic_tools_plugin_version` to pin: the marketplace manifest must declare
  exactly that version or provisioning fails.
- **The seed is read-only.** It is installed root-owned, directories `0755` and
  files `0644` with existing executables preserved. Claude Code never writes to
  it and disables auto-update for the marketplaces it finds there, so
  `/plugin marketplace update` and `/plugin marketplace remove` fail against a
  seeded marketplace by design. **Updating the catalog means rebuilding the
  image.**
- **A seeded marketplace wins over a declared one of the same name.** A project
  that declares the marketplace itself still gets the seed copy, and overriding
  the seeded version means `/plugin disable` on the seeded plugin first. A
  project that _is_ the catalog's source should instead opt out entirely by
  setting `CLAUDE_CODE_PLUGIN_SEED_DIR` to `""` in its container environment.
- **Registering a marketplace does not enable its plugin.** Claude Code takes
  that from `enabledPlugins`, so the role also declares the plugin in the user's
  `settings.json` (`agentic_tools_seed_enable_plugin`). Without it a container
  opened on a project with no `.claude/` configuration would see nothing.

Codex has no seed mechanism; it reads personal skills from `$CODEX_HOME/skills`.
The role copies the skills out of the seeded plugin — not out of the source tree,
so the two halves cannot drift — and symlinks `~/.codex/skills` at them. A
container that mounts a volume over the Codex home shadows that symlink, so
re-creating it after the mount is the consuming project's job.

The seed deliberately lives outside `$HOME`, because `~/.claude` and `~/.codex`
are commonly mounted as volumes.

## Example Usage

```yaml
- name: Install agentic tools
  hosts: all
  become: true
  roles:
    - {
        role: agentic_tools,
        tags: ['agentic_tools'],
        when: install_agentic_tools | default(false) | bool,
      }
```

## Variables

### cc-filter

| Variable                                  | Default                    | Description                                        |
| ----------------------------------------- | -------------------------- | -------------------------------------------------- |
| `agentic_tools_cc_filter_install`         | `true`                     | Install the cc-filter binary.                      |
| `agentic_tools_cc_filter_version`         | `v0.0.6`                   | cc-filter release tag to download.                 |
| `agentic_tools_cc_filter_install_path`    | `/usr/local/bin/cc-filter` | Destination for the cc-filter binary.              |
| `agentic_tools_cc_filter_binary_mode`     | `"0755"`                   | File mode for the installed binary.                |
| `agentic_tools_cc_filter_checksums`       | per-arch sha256 map        | Expected binary checksums; bump with the version.  |
| `agentic_tools_cc_filter_configure_hooks` | `true`                     | Merge cc-filter hooks into Claude `settings.json`. |
| `agentic_tools_cc_filter_download_url`    | derived from version/arch  | Override to pin a custom binary URL.               |

### Catalog seed

| Variable                                  | Default                           | Description                                                                    |
| ----------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------ |
| `agentic_tools_seed_plugins`              | `false`                           | Seed the agent catalog into the image.                                         |
| `agentic_tools_seed_source_dir`           | the repository root               | Tree whose root holds the marketplace manifest to seed from.                   |
| `agentic_tools_seed_marketplace_manifest` | `.claude-plugin/marketplace.json` | Manifest path within that tree.                                                |
| `agentic_tools_plugin_name`               | `agentdev`                        | Plugin to install out of the manifest.                                         |
| `agentic_tools_plugin_version`            | `""`                              | Version pin; the manifest must declare it. Empty means "whatever it declares". |
| `agentic_tools_seed_root`                 | `/opt/agentdev-seed`              | Root of the seeded tree.                                                       |
| `agentic_tools_plugin_seed_dir`           | `<seed root>/claude`              | Value for `CLAUDE_CODE_PLUGIN_SEED_DIR`.                                       |
| `agentic_tools_seed_enable_plugin`        | `true`                            | Declare the plugin in the user's `enabledPlugins`.                             |
| `agentic_tools_seed_codex_skills`         | `true`                            | Also seed the catalog's skills for Codex.                                      |
| `agentic_tools_codex_skills_seed_dir`     | `<seed root>/codex/skills`        | Where the Codex half is installed.                                             |
| `agentic_tools_seed_codex_skills_link`    | `{{ user_home }}/.codex/skills`   | Symlink pointed at it.                                                         |
| `agentic_tools_claude_bin`                | `/usr/local/bin/claude`           | Claude Code binary; seeding is skipped when it is absent.                      |
| `agentic_tools_seed_mode`                 | `u=rwX,go=rX`                     | Permissions applied across the seed.                                           |

## Required External Variables

These variables are not defined by this role and must be supplied by the
playbook or inventory (the `extra_facts` and `dev_user_setup` roles provide them
in this repository):

| Variable                                    | Description                                                            |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| `system_arch`                               | Target CPU architecture (`amd64` or `arm64`) for the binary URL.       |
| `user_home`                                 | Home directory of the target user (locates `~/.claude/settings.json`). |
| `dev_user_setup_uid` / `dev_user_setup_gid` | UID/GID used for ownership of the Claude config files.                 |
| `dev_user`                                  | Owner of the seeded catalog's Claude settings and Codex symlink.       |
