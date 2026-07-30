# shellcheck shell=bash
# Sourced by the other scripts in this directory; not executable on its own.
script_dir=$(dirname "${BASH_SOURCE[0]}")
root_dir=$(cd "$(dirname "$script_dir")" && pwd)
export root_dir

# Python sources linted and formatted by this repo's tooling.
export sources_dir="$root_dir/py_packages"

isCI()
{
  test -n "${CI:-}"
}
