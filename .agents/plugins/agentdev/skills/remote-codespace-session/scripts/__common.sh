#!/usr/bin/env bash

# Shared helpers for the remote-codespace-session skill scripts.
# This file is meant to be sourced, not executed directly:
#   source "$(dirname -- "${BASH_SOURCE[0]}")/__common.sh"

set -euo pipefail

skill_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_root_dir="$(cd -- "${skill_script_dir}/.." && pwd)"

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

# require_codespace_auth below is shared by every script in this skill, so the
# situation it reports is declared once, here: all four scripts name an
# under-scoped token CODESPACE_SCOPE_MISSING and exit 3 for it, and declare
# their own outcomes from 4 upward.
RESULT_CODES+=("3=CODESPACE_SCOPE_MISSING")

require_git_repo() {
  if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    print_error "This script must be run inside a Git repository."
    quit_by_code 2
  fi
}

require_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    print_error "The GitHub CLI ('gh') is required but was not found on PATH."
    quit_by_code 2
  fi
}

require_rsync() {
  if ! command -v rsync >/dev/null 2>&1; then
    print_error "'rsync' is required for the dirty-tree sync path but was not found on PATH. Install it locally (e.g. 'apt-get install -y rsync'); it is pre-installed in the codespace image on the remote end."
    quit_by_code 2
  fi
}

require_codespace_auth() {
  local err
  if ! err="$(gh codespace list --json name -q 'length' 2>&1 >/dev/null)"; then
    if printf '%s' "${err}" | grep -qiE '403|scope'; then
      print_error "gh is authenticated but the token is missing the 'codespace' OAuth scope. This skill needs a token with 'repo' + 'codespace' scopes (set GH_TOKEN/GITHUB_TOKEN, or run 'gh auth login' with those scopes)."
      quit_by_code 3
    fi
    print_error "gh is not authenticated. Run 'gh auth status' to check, then 'gh auth login'."
    quit_by_code 2
  fi
}

# Reject a non-numeric or out-of-range option value during argument parsing, so
# it becomes a PREFLIGHT_ERROR instead of a 'sleep' crash or an endless poll
# loop later on. '10#' forces base 10, so a value like 08 is not read as octal.
require_int_min() {
  local flag="$1" value="$2" min="$3"
  if [[ ! "${value}" =~ ^[0-9]+$ ]] || (( 10#${value} < min )); then
    print_error "${flag} expects an integer >= ${min}, got: ${value}"
    quit_by_code 2
  fi
}

current_branch() {
  git rev-parse --abbrev-ref HEAD
}

# The gh lookups below are used after require_codespace_auth has proven gh
# works, so a failure here is a broken call rather than a missing setup. They
# return non-zero instead of letting `set -e` end the run with gh's own exit
# status, which would otherwise be emitted as a script code that means
# something else entirely (gh exits 4 on auth trouble, for instance).
resolve_owner_repo() {
  local value
  if ! value="$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>/dev/null)" \
    || [[ -z "${value}" ]]; then
    print_error "Could not resolve the GitHub repository for this checkout. Check 'gh repo view'."
    return 1
  fi
  printf '%s' "${value}"
}

repo_name() {
  local value
  if ! value="$(gh repo view --json name -q '.name' 2>/dev/null)" || [[ -z "${value}" ]]; then
    print_error "Could not resolve the GitHub repository name for this checkout. Check 'gh repo view'."
    return 1
  fi
  printf '%s' "${value}"
}

branch_slug() {
  # Truncated to 40 chars with no collision handling: two branches whose
  # sanitized names share the same 40-char prefix map to the same
  # Codespace display name, and codespace-ensure.sh will silently reuse it.
  local branch_name="$1"
  printf '%s' "${branch_name}" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -e 's/[^a-z0-9-]\{1,\}/-/g' -e 's/^-\{1,\}//' -e 's/-\{1,\}$//' \
    | cut -c1-40
}

codespace_display_name() {
  local branch_name="$1"
  printf 'agent-%s' "$(branch_slug "${branch_name}")"
}

# GitHub Codespaces clones the repository into /workspaces/<repo-name> and
# runs the devcontainer from there. Derive that remote path from the repo name
# rather than hardcoding it, so it holds regardless of where the local
# docker-compose bind mount puts the workspace.
codespace_workspace_dir() {
  local name
  name="$(repo_name)" || return 1
  printf '/workspaces/%s' "${name}"
}

repo_root_tmp_dir() {
  local tmp_dir
  tmp_dir="$(git rev-parse --show-toplevel)/.tmp"
  mkdir -p "${tmp_dir}"
  printf '%s' "${tmp_dir}"
}

codespace_name_file() {
  printf '%s/codespace-name' "$(repo_root_tmp_dir)"
}

ssh_config_file() {
  printf '%s/codespace-ssh-config' "$(repo_root_tmp_dir)"
}

sync_exclude_file() {
  printf '%s/codespace-sync-exclude' "$(repo_root_tmp_dir)"
}

write_codespace_name() {
  local name="$1"
  printf '%s' "${name}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' > "$(codespace_name_file)"
}

# Returns non-zero when no name was recorded. Callers run it as
# `name="$(read_codespace_name)" || quit_by_code 2` so the RESULT line is
# emitted by the script itself rather than by the EXIT trap.
read_codespace_name() {
  local name_file
  name_file="$(codespace_name_file)"
  if [[ ! -s "${name_file}" ]]; then
    print_error "No codespace name recorded. Run codespace-ensure.sh first."
    return 1
  fi
  sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' < "${name_file}"
}

codespace_lookup_by_display_name() {
  local owner_repo="$1"
  local display_name="$2"
  local names
  names="$(gh codespace list -R "${owner_repo}" --json name,displayName \
    -q ".[] | select(.displayName==\"${display_name}\") | .name" 2>/dev/null)" || return 1
  printf '%s' "${names}" | head -n1
}

codespace_state_by_name() {
  local owner_repo="$1"
  local name="$2"
  local states
  states="$(gh codespace list -R "${owner_repo}" --json name,state \
    -q ".[] | select(.name==\"${name}\") | .state" 2>/dev/null)" || return 1
  printf '%s' "${states}" | head -n1
}

show_help_header() {
  local description="$1"

  printf '%s\n\n' "${description}"
  printf 'Skill root: %s\n' "${skill_root_dir}"
}
