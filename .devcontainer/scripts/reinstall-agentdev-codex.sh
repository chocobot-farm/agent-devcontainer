#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

marketplace_json="$repo_root/.agents/plugins/marketplace.json"
marketplace_name="$(jq -er '.name' "$marketplace_json")"
plugin_name="$(jq -er '.plugins[0].name' "$marketplace_json")"

# Remove the marketplace declared by this checkout plus any marketplace still
# registered under an older name but pointing at the same root. Otherwise a
# marketplace rename can leave a stale plugin installation and cache behind.
mapfile -t stale_names < <(
  codex plugin marketplace list --json \
    | jq -r --arg root "$repo_root" '
        .marketplaces[]
        | select(.root == $root or .marketplaceSource.source == $root)
        | .name
      '
)

while read -r name; do
  [[ -n "$name" ]] || continue
  codex plugin remove "$plugin_name@$name" || true
  codex plugin marketplace remove "$name" || true
done < <(printf '%s\n' "$marketplace_name" "${stale_names[@]}" | sort -u)

codex plugin marketplace add "$repo_root"
codex plugin add "$plugin_name@$marketplace_name"
