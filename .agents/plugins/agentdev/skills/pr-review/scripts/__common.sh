#!/usr/bin/env bash

set -euo pipefail

print_error() {
  printf 'ERROR: %s\n' "$*" >&2
}

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

# A script stopped by `set -e` or a bare `exit` never reaches quit_by_code. The
# EXIT trap keeps the RESULT line total without altering the exit status.
# HUP, INT, and TERM need explicit traps because EXIT may otherwise observe a
# stale zero status; normalize them to 1 so the run reports SCRIPT_FAILURE.
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
trap 'exit 1' HUP INT TERM

require_arg() {
  local name="$1" value="$2"
  if [[ -z "${value}" ]]; then
    print_error "Missing required argument: ${name}"
    quit_by_code 2
  fi
}

require_gh() {
  command -v gh >/dev/null 2>&1 || { print_error "gh CLI not found on PATH."; quit_by_code 2; }
  gh auth status >/dev/null 2>&1 || { print_error "gh is not authenticated."; quit_by_code 2; }
}

require_jq() {
  command -v jq >/dev/null 2>&1 || { print_error "jq not found on PATH."; quit_by_code 2; }
}

require_body_file() {
  local body_file="$1"
  if [[ ! -f "${body_file}" ]]; then
    print_error "Body file not found: ${body_file}. Write the text with the Write tool first, then pass its path."
    quit_by_code 2
  fi
}

# Prints "<owner>/<name>" for the current repo
resolve_repo() {
  gh repo view --json nameWithOwner -q .nameWithOwner
}
