#!/usr/bin/env bash
set -exuo pipefail

workspace="${DEV_WORKSPACE_FOLDER:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

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
"$workspace/scripts/uv-sync.sh"

# Register and install the repository's Codex plugin after the workspace and
# persistent ~/.codex volume are mounted. Both commands are idempotent, so a
# rebuild also refreshes the local plugin cache from the canonical plugin tree.
codex plugin marketplace add "$workspace"
codex plugin add agentdev@agent-devcontainer
