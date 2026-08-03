---
name: sync-pr-description
description: 'Refresh an existing GitHub pull request title and body so they match the current branch, then push the branch. Use when asked to sync, update, refresh, or regenerate a PR description or title for the branch in the working tree, including after new commits land on it. Stops when the branch has no pull request; creating a PR belongs to /agentdev:open-pr, and formatting, committing, and base-branch sync belong to their own skills.'
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/*)
---

# Sync PR Description

Bring an already-open pull request back in sync with the branch it points at:
find the PR for the current branch, regenerate its title and body from the
branch's real changes, push the branch, and edit the PR in place.

Sync the PR text for the branch exactly as it stands. Unlike
[open-pr](../open-pr/SKILL.md), do **not** reformat, commit, or merge
`origin/main` first, and do not create a pull request that is missing.

## Bundled Scripts

- [find-branch-pr.sh](scripts/find-branch-pr.sh) resolves the single pull
  request whose head is the current branch, and fails loudly when there is
  none or more than one.
- [push-branch.sh](scripts/push-branch.sh) pushes the branch to its PR head ref
  without rewriting history.

## Workflow

### 1. Locate the Pull Request — Hard Stop When Absent

```bash
${CLAUDE_SKILL_DIR}/scripts/find-branch-pr.sh
```

On success the script prints `PR_NUMBER`, `PR_URL`, `PR_STATE`, `PR_IS_DRAFT`,
`PR_BASE`, `PR_HEAD`, and `PR_TITLE`. Keep `PR_NUMBER` and `PR_BASE` for the
remaining steps.

Handle non-zero exits by stopping, not by improvising:

| Exit | Meaning                                                    | Action                                                                                                                    |
| ---- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `3`  | No open PR for this branch                                 | **STOP.** Report that there is nothing to sync and name `/agentdev:open-pr` as the way to create one. Do not create a PR. |
| `4`  | Several PRs share this head branch                         | **STOP.** Show the candidates and ask which PR to update.                                                                 |
| `5`  | Current branch is `main` or `master`                       | **STOP.** Report that a PR head must be a feature branch.                                                                 |
| `2`  | Not a repo, detached HEAD, `gh` missing or unauthenticated | **STOP.** Report the reported blocker verbatim.                                                                           |

Add `--state all` only when the user explicitly asks to sync a closed or merged
PR.

### 2. Generate the New Title and Body

Follow [generate-pr-description](../generate-pr-description/SKILL.md) to produce
the body, using `PR_BASE` as the base ref rather than assuming `main`:

```bash
git fetch --quiet origin "${PR_BASE}"
merge_base="$(git merge-base "origin/${PR_BASE}" HEAD)"
```

Describe the committed branch, which is what the PR will contain. Uncommitted
working-tree changes are out of scope: mention them in the final report rather
than writing them into the body or committing them here.

Derive the title from the same analysis: a concise, outcome-focused summary of
the branch. Preserve the existing title's issue prefix (for example `[#42]`)
when it has one, and keep the existing title if it already describes the branch
accurately — a sync should not churn a good title.

Do not pause for approval of the draft. The user invoked this skill to have the
PR updated, so continue straight to the push and edit.

### 3. Push the Branch

```bash
${CLAUDE_SKILL_DIR}/scripts/push-branch.sh
```

The script exits `0` when it pushed or the head ref was already current. On exit
`3` (behind or diverged) or `4` (push rejected), stop and report the recovery
commands it printed. Never force-push and never update the branch ref through a
GitHub API or MCP tool — reconcile locally with
[update-branch](../update-branch/SKILL.md) instead, then rerun this skill.

The push comes before the edit so the PR body never describes commits that are
not yet on the remote head.

### 4. Update the Title and Body

Write the body to a file under `./.tmp/` (relative to the repository root;
create the directory if missing) so shell quoting cannot corrupt Markdown, then
edit the PR:

```bash
gh pr edit <PR_NUMBER> --title "<new title>" --body-file ./.tmp/pr-body.md
```

Pass `--title` only when the title actually changed. Leave draft state, base
branch, labels, reviewers, and assignees untouched — this skill syncs text
only.

### 5. Report

Confirm with the PR URL, and state whether the title changed, whether the body
changed, and whether the push moved the head ref.

## Ownership

The pull request belongs to the user. Do not add AI authorship, co-authorship,
or "generated by" attributions to the title or body unless the user asks.
