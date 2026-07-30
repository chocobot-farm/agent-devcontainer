#!/usr/bin/env bash

set -euo pipefail

script_dir=$(dirname "$0")
# shellcheck source=/dev/null
source "$script_dir/ruff-commands.sh"

# sources_dir/root_dir come from __utils.sh; ruff_* come from ruff-commands.sh.
# shellcheck disable=SC2154
all_sources=("$sources_dir" "$root_dir/scripts")

# shellcheck disable=SC2154,SC2086 # word splitting is intended for the ruff_* commands
$ruff_format "${all_sources[@]}"
# shellcheck disable=SC2154,SC2086
$ruff_lint_fix "${all_sources[@]}"
# shellcheck disable=SC2154,SC2086
$ruff_isort "${all_sources[@]}"
