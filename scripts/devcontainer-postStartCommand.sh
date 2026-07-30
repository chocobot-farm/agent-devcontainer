#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/devcontainer-setup-pre-commit.sh"
"$script_dir/devcontainer-setup-keyring.sh"
"$script_dir/devcontainer-firewall.sh"
/start-xpra.sh --background
"$script_dir/devcontainer-configure-codex.py"
