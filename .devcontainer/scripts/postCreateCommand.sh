#!/usr/bin/env bash
set -exuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${DEV_WORKSPACE_FOLDER:-$(cd "$script_dir/../.." && pwd)}"

# Named volumes are created root-owned by the daemon; make sure the container
# user owns the mount points it writes to.
sudo chown -R root:root \
    "$workspace/.cache" \
    /uv

# ~/.claude.json can't be backed directly by a named volume (Docker volumes are always
# directory-backed, so mounting one at a file path materializes an empty directory
# there instead of the file Claude Code expects). Persist it as a plain file inside the
# already-mounted agentdev-claude volume and symlink it into place instead.
claude_json_target="/root/.claude/claude.json"
if [[ -f /root/.claude.json && ! -L /root/.claude.json ]]; then
    mv /root/.claude.json "$claude_json_target"
elif [[ ! -e "$claude_json_target" ]]; then
    echo '{}' >"$claude_json_target"
fi
ln -sf "$claude_json_target" /root/.claude.json

# Sync the project environment into the container's .venv directory so that
# extension settings are valid when the container is rebuilt. This is a no-op if the environment is already up to date.
"$script_dir/uv-sync.sh"

# The agentdev-codex volume mounts over the ~/.codex/skills link the image creates,
# so restore it now that the volume is in place. No-op in this repository, which
# opts out of the seed because it is the catalog's source.
"$script_dir/link-codex-seed-skills.sh"

# Register and install the repository's Codex/Claude plugin after the workspace and
# persistent ~/.codex and ~/.claude volumes are mounted.
"$script_dir/reinstall-agentdev-codex.sh"
"$script_dir/reinstall-agentdev-claude.sh"
