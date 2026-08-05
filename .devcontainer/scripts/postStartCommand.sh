#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$script_dir/setup-pre-commit.sh"
"$script_dir/setup-keyring.sh"
"$script_dir/firewall.sh"
/start-xpra.sh --background
"$script_dir/configure-codex.py"
"$script_dir/reinstall-agentdev-codex.sh"
"$script_dir/reinstall-agentdev-claude.sh"
