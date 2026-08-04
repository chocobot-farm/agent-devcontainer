#!/usr/bin/env bash

set -euo pipefail

source_ref=""
merge_message=""

print_error() {
  printf 'ERROR: %s\n' "$*" >&2
}

# Canonical result-code block (skill-scripts skill). This script is standalone
# and has no __common.sh, so the shared helpers live here.
#
# Codes 0, 1, and 2 mean the same thing in every skill script. A script
# declares its own outcomes from 3 upward by appending to RESULT_CODES:
#
#   RESULT_CODES+=("3=NO_PR_FOUND" "4=MULTIPLE_PRS")
#
# A later entry overrides an earlier one for the same code, so a script may
# also give 2 a more specific name.
RESULT_CODES=(
  "0=SUCCESS"
  "1=SCRIPT_FAILURE"
  "2=PREFLIGHT_ERROR"
)

result_emitted=0

emit_result() {
  local code="$1"
  local entry
  local result="UNKNOWN_CODE_${code}"

  for entry in ${RESULT_CODES[@]+"${RESULT_CODES[@]}"}; do
    if [[ "${entry%%=*}" == "${code}" ]]; then
      result="${entry#*=}"
    fi
  done

  result_emitted=1
  printf 'RESULT=%s\n' "${result}"
}

# Exit with `code` after naming it. Use for every terminal path, success
# included, so RESULT is always the last line of stdout.
quit_by_code() {
  emit_result "$1"
  exit "$1"
}

# A script stopped by `set -e`, a signal, or a bare `exit` never reaches
# quit_by_code. The trap keeps the RESULT line total; it does not alter the
# exit status.
#
# The directive suppresses a false positive that only appears when this block
# lives in the script instead of a sourced __common.sh: because the last
# top-level command exits, ShellCheck reads the handler as dead code (SC2317 in
# 0.9, SC2329 in 0.11). It is invoked by the EXIT trap below.
# shellcheck disable=SC2317,SC2329
report_unhandled_exit() {
  local code=$?
  if [[ "${result_emitted}" -eq 0 ]]; then
    emit_result "${code}"
  fi
}

trap report_unhandled_exit EXIT

# These numbers and names are shared with update-branch.sh, which execs this
# script and passes its verdict straight through. Keep the two tables aligned.
RESULT_CODES+=("3=ALREADY_UP_TO_DATE" "4=MERGE_CONFLICTS")

usage() {
  cat <<'EOF'
Merge a local Git ref into the current branch with a non-fast-forward merge.

Usage:
  git-merge-resolve.sh [--message <text>] <source-ref>

Options:
  --message <text>  Merge commit message. Defaults to a generated message.
  -h, --help        Show this help text.

Output (key=value lines):
  RESULT
  Once preflight passes also: DESTINATION, SOURCE

Results (RESULT / exit code):
  SUCCESS            0  Merge succeeded
  ALREADY_UP_TO_DATE 3  Source ref is already merged into HEAD
  MERGE_CONFLICTS    4  Conflicts detected; resolve and commit them
  PREFLIGHT_ERROR    2  Usage, repository, ref, or working-tree preflight
                        failed, or the merge failed with no unresolved paths
  SCRIPT_FAILURE     1  Unhandled error

Examples:
  ${CLAUDE_SKILL_DIR}/scripts/git-merge-resolve.sh topic
  ${CLAUDE_SKILL_DIR}/scripts/git-merge-resolve.sh \
    --message "Merge origin/main into feature" origin/main
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message)
      [[ $# -ge 2 ]] || { print_error "Missing value for --message"; quit_by_code 2; }
      merge_message="$2"
      shift 2
      ;;
    -h|--help)
      usage
      quit_by_code 0
      ;;
    --*)
      print_error "Unknown option: $1"
      usage >&2
      quit_by_code 2
      ;;
    *)
      if [[ -n "${source_ref}" ]]; then
        print_error "Only one source ref may be supplied."
        usage >&2
        quit_by_code 2
      fi
      source_ref="$1"
      shift
      ;;
  esac
done

if [[ -z "${source_ref}" ]]; then
  print_error "A source ref is required."
  usage >&2
  quit_by_code 2
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  print_error "This script must be run inside a Git repository."
  quit_by_code 2
fi

if [[ "$(git rev-parse --abbrev-ref HEAD)" == "HEAD" ]]; then
  print_error "Detached HEAD cannot receive this merge. Check out a branch first."
  quit_by_code 2
fi

if [[ -f "$(git rev-parse --git-path MERGE_HEAD)" ]]; then
  print_error "A merge is already in progress. Resolve or complete it first."
  git status --short >&2
  quit_by_code 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
  print_error "Working tree is dirty. Commit or stash changes before merging."
  git status --short >&2
  quit_by_code 2
fi

if ! git rev-parse --verify --quiet "${source_ref}^{commit}" >/dev/null; then
  print_error "Source ref does not resolve to a commit: ${source_ref}"
  quit_by_code 2
fi

destination_branch="$(git rev-parse --abbrev-ref HEAD)"
source_sha="$(git rev-parse "${source_ref}^{commit}")"

printf 'DESTINATION=%s\n' "${destination_branch}"
printf 'SOURCE=%s\n' "${source_ref}"

if git merge-base --is-ancestor "${source_sha}" HEAD; then
  printf '%s is already merged into %s.\n' \
    "${source_ref}" "${destination_branch}" >&2
  quit_by_code 3
fi

if [[ -z "${merge_message}" ]]; then
  merge_message="Merge ${source_ref} into ${destination_branch}"
fi

printf 'Merging %s into %s...\n' "${source_ref}" "${destination_branch}" >&2
if git merge --no-ff "${source_ref}" --message "${merge_message}"; then
  git log --oneline --decorate -n 5
  quit_by_code 0
fi

conflicted_files="$(git diff --name-only --diff-filter=U)"
if [[ -z "${conflicted_files}" ]]; then
  print_error "Merge failed without unresolved paths. Inspect Git output and status."
  git status --short >&2
  quit_by_code 2
fi

print_error "Merge conflicts detected. Resolve the conflicts listed below."
printf '\nConflicted files:\n' >&2
printf '%s\n' "${conflicted_files}" >&2
quit_by_code 4
