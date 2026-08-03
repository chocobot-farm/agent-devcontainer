---
name: skill-scripts
description: "Write and document a skill's bundled scripts so their outcome is readable by both a shell caller and an agent — a shared exit-code vocabulary, a RESULT= enum line on stdout, and the quit_by_code helper in __common.sh. Use when adding or editing a script under a skill's scripts/ directory, choosing or renumbering its exit codes, deciding what it prints, or wiring a SKILL.md step to branch on a script's outcome. Keywords: exit code, RESULT, quit_by_code, __common.sh, script output contract."
---

# Skill Script Result Contract

A bundled script has two callers with different needs. A shell or test caller
branches on `$?` and needs numeric codes. An agent reads the tool result and
needs an outcome it can act on without resolving a bare number against a table
printed thousands of tokens earlier. Serve both: **keep the exit code, and name
it on stdout.**

Apply this to every script under a skill's `scripts/` directory.

## The Contract

1. **stdout is machine-readable `KEY=value` lines.** Human explanation,
   diagnostics, and errors go to stderr via `print_error`.
2. **The last line of stdout is always `RESULT=<NAME>`**, on every path
   including success, help, and crashes.
3. **The exit code matches the RESULT**, and stays a stable part of the
   script's interface.

## Reserved Codes

| Code    | Name              | Meaning                                                                                                                                                                         |
| ------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0`     | `SUCCESS`         | The script did what it was asked.                                                                                                                                               |
| `1`     | `SCRIPT_FAILURE`  | The script broke. **Never assign `1` a deliberate meaning** — `set -e`, a signal, and an unhandled error all produce it, so a deliberate `1` is indistinguishable from a crash. |
| `2`     | `PREFLIGHT_ERROR` | Bad usage, or the environment cannot support the operation at all: not a repo, detached HEAD, missing required argument.                                                        |
| `3`–`9` | script-specific   | Outcomes the caller must branch on. Number them in the order the workflow meets them.                                                                                           |

Stay at or below `125`. `126`, `127`, and `128+N` are shell-reserved and will
be produced by the shell itself.

## Numbers Are Local, Names Are Shared

Do not try to make one number mean one thing across every skill — `3` is
already "no PR found" in one script and "already up to date" in another, and
forcing a global numbering makes each script's own table arbitrary.

Share the **names** instead. When two scripts hit the same situation, give it
the same `RESULT` name even if the numbers differ: `PROTECTED_BRANCH`,
`GH_UNAVAILABLE`, `ALREADY_UP_TO_DATE`, `PUSH_REJECTED`. That is the whole
reason the string exists — it is unambiguous where a reused number is not.

Name the **outcome**, not the remedy: `NO_PR_FOUND`, not `CREATE_PR_NEXT`. The
SKILL.md table decides the remedy; the script only reports what it saw.
Use `SCREAMING_SNAKE_CASE`, and no `RESULT_` prefix — the key already says it.

## Give a Distinct Code to Anything the Caller Handles Differently

The point of a separate code is a separate reaction. Split a code out when the
workflow's response differs — most importantly, **a failure a fallback can
rescue must not share a code with a hard stop.** If a skill falls back to a
GitHub MCP server when `gh` is unusable, then a missing `gh`, an
unauthenticated `gh`, _and_ a `gh` API call that failed on scope or network all
belong to the fallback code, not to `PREFLIGHT_ERROR`.

Conversely, do not mint a code the caller reacts to identically. Two forms of
the same dead end are one `PREFLIGHT_ERROR` with different stderr text.

## Implementation

Copy [assets/result-codes.sh](assets/result-codes.sh) verbatim into the skill's
`scripts/__common.sh`. Skills do not source across each other's directories —
each `__common.sh` already carries its own copy of the shared helpers.

In the script, declare the script-specific codes right after sourcing, then
call `quit_by_code` on every terminal path:

```bash
source "${script_dir}/__common.sh"

RESULT_CODES+=("3=NO_PR_FOUND" "4=MULTIPLE_PRS" "5=PROTECTED_BRANCH" "6=GH_UNAVAILABLE")

[[ $# -ge 2 ]] || { print_error "Missing value for --branch"; quit_by_code 2; }
...
printf 'PR_FOUND=false\n'
quit_by_code 3
```

`quit_by_code 0` replaces a bare `exit 0`, including at the end of the happy
path and after `--help`. An uncaught failure still prints
`RESULT=SCRIPT_FAILURE` through the `EXIT` trap, so a reader never sees a run
with no verdict.

## Document It Twice

**In the script's `--help`**, replace the `Exit codes:` block with a paired
table, and list `RESULT` first in the output keys:

```text
Output (key=value lines):
  RESULT, HEAD_BRANCH, PR_FOUND
  On a match also: PR_NUMBER, PR_URL, PR_STATE, PR_IS_DRAFT, PR_BASE, PR_TITLE

Results (RESULT / exit code):
  SUCCESS           0  Exactly one matching pull request was found
  NO_PR_FOUND       3  No matching pull request exists
  MULTIPLE_PRS      4  Multiple matching pull requests exist
  PROTECTED_BRANCH  5  Branch is a protected default branch
  GH_UNAVAILABLE    6  gh is missing, unauthenticated, or its API call failed
  PREFLIGHT_ERROR   2  Usage or preflight error (not a repo, detached HEAD)
  SCRIPT_FAILURE    1  Unhandled error
```

Order by the workflow, not by number: success, then the outcomes a caller acts
on, then the error codes.

**In the consuming `SKILL.md`**, key the decision table on `RESULT` with the
code as a secondary column, so the agent matches on the string it just read:

```markdown
| RESULT         | Exit | Action                                            |
| -------------- | ---- | ------------------------------------------------- |
| `SUCCESS`      | `0`  | **Update mode.** Keep `PR_NUMBER`, `PR_BASE`, ... |
| `NO_PR_FOUND`  | `3`  | **Create mode.** Continue and create the PR ...   |
| `MULTIPLE_PRS` | `4`  | **STOP.** Show the candidates and ask which ...   |
```

State the reaction to `SCRIPT_FAILURE` and `PREFLIGHT_ERROR` too, even if it is
just "STOP and report the blocker verbatim".

## Definition of Done

- Every terminal path exits through `quit_by_code`; no bare `exit N` remains
  outside `__common.sh`.
- Nothing deliberately exits `1`.
- Each code appears once in the script with one meaning.
- Recurring situations use the same `RESULT` name as sibling skills.
- The `--help` table and the SKILL.md table list the same names and codes as
  the script.
- The script passes `shellcheck -x` and has been run for at least its success
  path and one branching failure path, with artifacts in `./.tmp/`.
