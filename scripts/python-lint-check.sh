#!/usr/bin/env bash
#
# Verify Python style compliance with ruff (the CI gate).
#
# python-reformat.sh applies ruff's formatter and autofixes; this script is the
# non-mutating check, so it is safe to run in CI or a pre-push hook.
#
# Usage:
#   scripts/python-lint-check.sh [PATH ...]
#
# With no arguments this checks the repository's Python sources. Pass explicit
# paths (files or directories) to scope the check for rapid iteration.
#
# Exits non-zero when ruff reports any violation.

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
source "$script_dir/__utils.sh"

if [ "$#" -gt 0 ]; then
  targets=("$@")
else
  # shellcheck disable=SC2154 # exported by __utils.sh
  targets=("$sources_dir" "$script_dir")
fi

# shellcheck source=/dev/null
# shellcheck disable=SC2154 # exported by __utils.sh
source "$root_dir/.venv/bin/activate"

ruff format --check --quiet "${targets[@]}"
ruff check --quiet "${targets[@]}"
