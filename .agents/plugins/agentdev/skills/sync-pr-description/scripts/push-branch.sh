#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${script_dir}/__common.sh"

remote_name="origin"

usage() {
  show_help_header "Push the current branch to its pull request head ref without rewriting history."
  cat <<'EOF'

Usage:
  push-branch.sh [--remote <name>]

Options:
  --remote <name>    Remote to push to when no upstream is configured. Default: origin
  -h, --help         Show this help text.

Exit codes:
  0  Pushed, or already up to date
  2  Usage or preflight error
  3  Branch is behind or diverged from its upstream
  4  Push failed
  5  Branch is a protected default branch
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      [[ $# -ge 2 ]] || { print_error "Missing value for --remote"; exit 2; }
      remote_name="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      print_error "Unknown argument: $1"
      usage >&2
      exit 2
      ;;
  esac
done

require_git_repo

branch_name="$(current_branch)"

if [[ "${branch_name}" == "HEAD" ]]; then
  print_error "Detached HEAD: check out the pull request branch before pushing."
  exit 2
fi

if is_default_branch "${branch_name}"; then
  print_error "Refusing to push from ${branch_name}; a pull request head must be a feature branch."
  exit 5
fi

printf 'BRANCH=%s\n' "${branch_name}"

if upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name "${branch_name}@{u}" 2>/dev/null)"; then
  upstream_remote="${upstream_ref%%/*}"
  upstream_branch="${upstream_ref#*/}"

  git fetch --quiet "${upstream_remote}" "${upstream_branch}" 2>/dev/null || true

  ahead_count="$(git rev-list --count "${upstream_ref}..${branch_name}")"
  behind_count="$(git rev-list --count "${branch_name}..${upstream_ref}")"

  printf 'UPSTREAM=%s\n' "${upstream_ref}"
  printf 'AHEAD=%s\n' "${ahead_count}"
  printf 'BEHIND=%s\n' "${behind_count}"

  if [[ "${behind_count}" -gt 0 ]]; then
    print_error "Local branch is behind its upstream; the pull request head would not fast-forward."
    printf 'Reconcile the branch first, then rerun:\n' >&2
    printf '  git pull --ff-only %s %s\n' "${upstream_remote}" "${upstream_branch}" >&2
    printf 'If the branches diverged, merge the upstream branch instead. Never force-push here.\n' >&2
    exit 3
  fi

  if [[ "${ahead_count}" -eq 0 ]]; then
    printf 'ACTION=none\n'
    printf 'RESULT=up-to-date\n'
    exit 0
  fi

  printf 'ACTION=push\n'
  if push_output="$(git push "${upstream_remote}" "refs/heads/${branch_name}:refs/heads/${upstream_branch}" 2>&1)"; then
    printf '%s\n' "${push_output}"
    printf 'RESULT=pushed\n'
    exit 0
  fi

  print_error "Git push failed. Check Git credentials and remote permissions."
  printf '%s\n' "${push_output}" >&2
  exit 4
fi

if ! git remote get-url "${remote_name}" >/dev/null 2>&1; then
  print_error "Remote not found: ${remote_name}"
  exit 2
fi

printf 'UPSTREAM=%s/%s\n' "${remote_name}" "${branch_name}"
printf 'ACTION=push-with-upstream\n'

if push_output="$(git push -u "${remote_name}" "${branch_name}" 2>&1)"; then
  printf '%s\n' "${push_output}"
  printf 'RESULT=pushed-with-upstream\n'
  exit 0
fi

print_error "Git push failed. Check Git credentials and remote permissions."
printf '%s\n' "${push_output}" >&2
exit 4
