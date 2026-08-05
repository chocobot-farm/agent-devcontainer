#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

marketplace_json="$repo_root/.claude-plugin/marketplace.json"
marketplace_name="$(jq -er '.name' "$marketplace_json")"
plugin_name="$(jq -er '.plugins[0].name' "$marketplace_json")@$marketplace_name"

# `claude plugin marketplace remove` only accepts a marketplace name, never a
# path. Collect the name this checkout currently declares plus any registered
# under an older name but still pointing here, so a rename does not leave a
# stale entry shadowing the new one. The removals omit --scope on purpose:
# a leftover declaration in user or local settings shadows the project one
# just as effectively, and `add` reports the stale name instead of re-reading
# marketplace.json.
known_marketplaces="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/known_marketplaces.json"
stale_names=()
if [[ -f "$known_marketplaces" ]]; then
  mapfile -t stale_names < <(
    jq -r --arg root "$repo_root" '
      to_entries[]
      | select(.value.source.path == $root or .value.installLocation == $root)
      | .key
    ' "$known_marketplaces"
  )
fi

while read -r name; do
  [[ -n "$name" ]] || continue
  claude plugin uninstall "${plugin_name%@*}@$name" --scope project || true
  claude plugin marketplace remove "$name" || true
done < <(printf '%s\n' "$marketplace_name" "${stale_names[@]}" | sort -u)

claude plugin marketplace add "$repo_root" --scope local
claude plugin install "$plugin_name" --scope local
