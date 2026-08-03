#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

cd "$repo_root"
claude plugin marketplace add "./." --scope project

plugin_name="agentdev@chocobot-farm"
claude plugin uninstall "$plugin_name" --scope project || true
claude plugin install "$plugin_name" --scope project
