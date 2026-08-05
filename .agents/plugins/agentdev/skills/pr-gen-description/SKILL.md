---
name: pr-gen-description
description: Generate comprehensive pull request description following /agentdev:code-review-standards with change analysis, testing strategy, and migration notes. Use when creating a PR, writing PR description, preparing for code review, or documenting technical decisions.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/*)
---

# Generate Pull Request Description

Generate a comprehensive PR description by analyzing the change set and filling the pull request template of the repository being worked in — `.github/pull_request_template.md`, or a file under `.github/PULL_REQUEST_TEMPLATE/`. Use [code-review-standards](../code-review-standards/) for wording and review conventions, and use the Coding Conventions section of that repository's root `AGENTS.md` only for shared quality expectations rather than repeating them here.

## When to Use This Skill

- Creating a pull request for code changes
- Need detailed PR description that explains changes
- Want to follow project conventions for PR documentation
- Preparing for code review
- Documenting technical decisions and assumptions

## Prerequisites

- Changes committed to a branch
- Understanding of what was changed and why
- Related GitHub issues identified (optional)
- Testing performed

## Inputs

- **Base Ref** or **Commit Range**: Default to the PR merge base with
  `origin/main`; accept an explicit base ref or range when the caller provides
  one. A caller updating an existing pull request passes that PR's base branch.
- **Related Issues**: GitHub issue numbers
- **Breaking Changes**: Yes/No
- **Migration Steps**: If breaking

## Bundled Scripts

Use this helper instead of retyping inline git commands:

- [review-git-changes.sh](scripts/review-git-changes.sh) prints the branch,
  working tree status, diff stat, patch, and commit log for the change set.

The last line of stdout is always `RESULT=<NAME>`; match on that name, not on a
bare number.

## Workflow

### Step 1: Analyze Git Changes

```bash
${CLAUDE_SKILL_DIR}/scripts/review-git-changes.sh
```

Pass `--base-ref <ref>` when the caller supplies a base other than
`origin/main`, or `--range <range>` for an explicit commit range. Add
`--stat-only` to skip the patch on a very large change set.

The script compares against the merge base rather than a raw `origin/main..HEAD`
range: when the branch and its base have diverged, PR review shows the changes
introduced by the head branch since that common ancestor.

Handle the result:

| RESULT            | Exit | Meaning                                                                  | Action                                                                                                                             |
| ----------------- | ---- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `SUCCESS`         | `0`  | The change report was printed                                            | Continue with Step 2.                                                                                                              |
| `NO_CHANGES`      | `3`  | Nothing to describe: no working tree changes and no commits in the range | **STOP.** Follow the **No changes** edge case instead of writing a description.                                                    |
| `PREFLIGHT_ERROR` | `2`  | Bad usage, not a repo, no commits, or an unknown ref                     | **STOP.** Fix the reported error — usually a wrong `--base-ref` or `--range`, or a base ref that has not been fetched — and rerun. |
| `SCRIPT_FAILURE`  | `1`  | The script broke                                                         | **STOP.** Report the blocker verbatim; do not retry or reconstruct the analysis with ad-hoc `git` commands.                        |

Categorize: new, modified, deleted, renamed.

Describe the committed branch, which is what the pull request will contain. The
script also prints uncommitted working-tree changes — report those to the caller
as out of scope instead of writing them into the description.

### Step 2: Identify Change Categories

Features, Bug Fixes, Refactoring, Tests, Documentation, Configuration, Performance, Security.

### Step 3: Extract Technical Details

For each significant change: purpose, approach, files affected, dependencies, side effects.

### Step 4: Identify Related Issues

Search commits and branch name for #123, GH-456. Link issues, design docs, related PRs.

### Step 5: Assess Testing Strategy

Unit tests, integration tests, manual testing, coverage impact.

### Step 6: Check Breaking Changes

API changes, config changes, dependency version changes, schema changes.

Identify any required migration work such as config changes, rollout order, data backfills, operator actions, or compatibility notes.

### Step 7: Generate The Description

Locate the repository's pull request template — `.github/pull_request_template.md`, or a file under `.github/PULL_REQUEST_TEMPLATE/` — and start from it, following the wording rules from [code-review-standards](../code-review-standards/). When the repository has no template, use the section list below as the structure instead. Remove sections that do not apply, and ensure the final PR description covers the same information required by the template:

- **Summary**: 2-3 sentences
- **What Changed**: Group related changes instead of listing files
- **Why**: User or system impact
- **How to Test**: Actual verification performed
- **Breaking Changes**: Only when applicable
- **Migration**: Required rollout, upgrade, backfill, or operator steps
- **Related**: Issues, design docs, or follow-up work

### Step 8: Review and Validate

Ensure completeness, technical accuracy, valid links, and that testing matches actual work. Confirm that the final description stays in sync with the repository's pull request template (or, when it has none, with the section list in Step 7) and does not repeat generic review or clean-code checklists from the referenced documents.

## Edge Cases

- **No changes**: the script reports `NO_CHANGES` and notes the empty change
  set on stderr. Report that there is nothing to describe and check the branch
  and commit range with the caller.
- **Too many changes**: Summarize categories, detail significant only
- **No tests**: Warn incomplete testing section
- **Multiple unrelated changes**: Suggest splitting PRs

## Related Resources

- The repository's pull request template: `.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/`
- [code-review-standards](../code-review-standards/)
- Coding Conventions in the repository's root `AGENTS.md`
