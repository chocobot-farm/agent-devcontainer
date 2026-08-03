#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${script_dir}/__common.sh"

branch_name=""
state_filter="open"

usage() {
  show_help_header "Find the pull request whose head is the current branch."
  cat <<'EOF'

Usage:
  find-branch-pr.sh [--branch <name>] [--state open|all]

Options:
  --branch <name>    Head branch to look up. Default: current branch
  --state <state>    PR state filter: open (default) or all
  -h, --help         Show this help text.

Output (key=value lines on success):
  PR_FOUND, PR_NUMBER, PR_URL, PR_STATE, PR_IS_DRAFT, PR_BASE, PR_HEAD, PR_TITLE

Exit codes:
  0  Exactly one matching pull request was found
  2  Usage or preflight error (not a repo, gh missing or unauthenticated)
  3  No matching pull request exists (the branch still needs one created)
  4  Multiple matching pull requests exist
  5  Branch is a protected default branch
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      [[ $# -ge 2 ]] || { print_error "Missing value for --branch"; exit 2; }
      branch_name="$2"
      shift 2
      ;;
    --state)
      [[ $# -ge 2 ]] || { print_error "Missing value for --state"; exit 2; }
      state_filter="$2"
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

case "${state_filter}" in
  open|all) ;;
  *)
    print_error "Unsupported --state value: ${state_filter} (use open or all)"
    exit 2
    ;;
esac

require_git_repo

if [[ -z "${branch_name}" ]]; then
  branch_name="$(current_branch)"
fi

if [[ "${branch_name}" == "HEAD" ]]; then
  print_error "Detached HEAD: check out the pull request branch before looking up its pull request."
  exit 2
fi

if is_default_branch "${branch_name}"; then
  print_error "Branch ${branch_name} is a protected default branch; a pull request head must be a feature branch."
  exit 5
fi

if ! command -v gh >/dev/null 2>&1; then
  print_error "GitHub CLI (gh) is not installed."
  exit 2
fi

if ! gh auth status >/dev/null 2>&1; then
  print_error "GitHub CLI is not authenticated. Run 'gh auth login' and retry."
  exit 2
fi

# A Go template keeps this dependent on `gh` alone, with no jq requirement.
# Each match starts with a PR_RECORD marker line so matches can be counted.
pr_template='{{range .}}PR_RECORD
PR_NUMBER={{.number}}
PR_URL={{.url}}
PR_STATE={{.state}}
PR_IS_DRAFT={{.isDraft}}
PR_BASE={{.baseRefName}}
PR_HEAD={{.headRefName}}
PR_TITLE={{.title}}
{{end}}'

pr_output=""
if ! pr_output="$(gh pr list \
  --head "${branch_name}" \
  --state "${state_filter}" \
  --json number,url,state,isDraft,baseRefName,headRefName,title \
  --template "${pr_template}" \
  2>&1)"; then
  print_error "gh pr list failed for branch ${branch_name}."
  printf '%s\n' "${pr_output}" >&2
  exit 2
fi

pr_count="$(printf '%s\n' "${pr_output}" | grep -c '^PR_RECORD$' || true)"

if [[ "${pr_count}" -eq 0 ]]; then
  printf 'PR_FOUND=false\n'
  printf 'No %s pull request found with head branch %s; the branch needs a new pull request.\n' \
    "${state_filter}" "${branch_name}" >&2
  exit 3
fi

if [[ "${pr_count}" -gt 1 ]]; then
  print_error "Found ${pr_count} pull requests with head branch '${branch_name}'; refusing to guess which one to update."
  printf '%s\n' "${pr_output}" >&2
  exit 4
fi

printf 'PR_FOUND=true\n'
printf '%s\n' "${pr_output}" | grep -v '^PR_RECORD$' | grep -v '^$'
