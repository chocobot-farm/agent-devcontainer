#!/usr/bin/env bash

# Canonical result-code block for skill scripts. Copy it verbatim into a
# skill's scripts/__common.sh; it is not sourced across skill directories.
#
# Every terminal path calls quit_by_code, so every run ends with a
# RESULT=<NAME> line on stdout that names the outcome without the reader
# having to resolve a bare number against a table.

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
report_unhandled_exit() {
  local code=$?
  if [[ "${result_emitted}" -eq 0 ]]; then
    emit_result "${code}"
  fi
}

trap report_unhandled_exit EXIT
