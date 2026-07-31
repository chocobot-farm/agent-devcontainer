# shellcheck shell=bash
# Sourced by the other scripts in this directory; not executable on its own.
#
# These scripts ship in the `agentdev` plugin, so their own location is the
# plugin cache rather than the repository being worked on. The target repository
# is therefore resolved from the working directory, never from $BASH_SOURCE.
root_dir=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
export root_dir

isCI()
{
  test -n "${CI:-}"
}
