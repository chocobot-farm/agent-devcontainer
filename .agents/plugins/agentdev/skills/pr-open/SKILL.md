---
name: pr-open
description: 'Create a GitHub pull request from conversation context — or refresh the branch existing PR in place — with accurate title/body generation, branch sync, and remote push. Use when asked to open/create/submit a PR, draft a pull request, sync or update a PR description, or finalize changes after implementation. Keywords: open pr, create pr, submit pr, update pr, sync pr description, pull request, github pr, draft pr, ready for review.'
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/*)
---

# Open PR

This skill instructs AI agents on how to create GitHub pull requests from conversation context
with meaningful titles and proper formatting. The AI agent
should analyze the conversation, extract PR details, and create the pull request directly
without pausing for confirmation.

When the current branch already has an open pull request, this skill updates
that pull request in place instead of creating a second one: the same title and
body generation runs, and the result is written to the existing PR.

## GitHub MCP Tools Required

This skill may use GitHub MCP tools for GitHub operations or `gh` CLI commands if available and authenticated.

Required MCP tools:

- `github/create_pull_request` - create the pull request

Optional MCP tools (for validation and follow-up):

- `github/list_issues` - list recent issues when issue number is missing
- `github/pull_request_read` - fetch PR details after creation

Existing-PR lookup uses the bundled `find-branch-pr.sh` script rather than
`github/list_pull_requests`, and the branch is always pushed with local `git`
through `push-branch.sh` — never through a GitHub API or MCP tool.

## PR Description Source of Truth

The PR body content **MUST** be generated using the
[pr-gen-description](../pr-gen-description/) skill.

The pr-open skill is responsible for:

- detecting whether the branch already has a pull request
- optional issue linking in title/body when issue context exists
- delegating mandatory formatting and validation to the `local-reformat` skill
- delegating staging and commit creation to the `git-commit` skill
- delegating branch sync with the base branch to the `update-branch` skill
- pushing the branch to its remote head ref
- GitHub PR creation through MCP, or PR title/body update through `gh`

## Bundled Scripts

Use these exact helper scripts instead of retyping inline shell commands:

- [find-branch-pr.sh](scripts/find-branch-pr.sh) resolves the single pull request whose head is the current branch, and fails loudly when more than one matches.
- [push-branch.sh](scripts/push-branch.sh) verifies upstream tracking, pushes the branch when needed, and blocks on divergence without ever rewriting history.

The detailed PR description structure, section requirements, and quality checks
are defined in the [pr-gen-description](../pr-gen-description/) skill
and **MUST NOT** be duplicated here.

## Workflow for AI Agents

When this skill is invoked, the AI agent **MUST** follow these steps:

### 1. Context Analysis Phase

Review the entire conversation history and git changes to extract PR details:

- Identify what work was completed during the conversation
- Review git diff and git status to see actual changes made
- Extract key details: what was changed, why, which files were affected
- Determine the type of changes (feature, bugfix, refactor, etc.)
- Check if there's a related issue number mentioned in the conversation (optional)

Context signals for PR type:

- Feature signals: new functionality added, new files created, capabilities extended
- Bugfix signals: fixed error, resolved issue, corrected behavior
- Refactor signals: improved code structure, reorganized code, better patterns
- Documentation signals: updated README, added comments, wrote guides
- Test signals: added test coverage, modified test cases

### 2. Existing Pull Request Detection

Before doing any work, resolve whether this branch already has a pull request:

```bash
${CLAUDE_SKILL_DIR}/scripts/find-branch-pr.sh
```

Exit codes decide the rest of the run:

| Exit | Meaning                                                    | Action                                                                                                         |
| ---- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `0`  | Exactly one open PR has this head branch                   | **Update mode.** Keep `PR_NUMBER`, `PR_BASE`, and `PR_TITLE`; the PR will be edited in place, never recreated. |
| `3`  | No open PR for this branch                                 | **Create mode.** Continue and create the PR at the end. Use `main` as the base unless the user says otherwise. |
| `4`  | Several PRs share this head branch                         | **STOP.** Show the candidates and ask which PR to update.                                                      |
| `5`  | Current branch is `main` or `master`                       | **STOP.** A PR head must be a feature branch — see the error handling section below.                           |
| `2`  | Not a repo, detached HEAD, `gh` missing or unauthenticated | **STOP.** Report the blocker verbatim.                                                                         |

In update mode, `PR_BASE` — not an assumed `main` — is the base branch for the
remaining steps. Pass `--state all` only when the user explicitly asks to work
against a closed or merged PR.

### 3. Mandatory Local Reformat

**CRITICAL:** Before reviewing, committing, or creating a PR, the AI agent
**MUST** invoke and follow the `local-reformat` skill.

Run every formatter and validation required by that skill. Do not substitute a
partial set of formatters or bypass failures. If `local-reformat` cannot
complete successfully, stop PR creation and report the actionable failure to
the user.

### 4. Commit Any Uncommitted PR Scope

After `local-reformat` completes successfully, inspect `git status`. If the
PR-scope changes are uncommitted, invoke and follow the `git-commit` skill to
stage only that scope and create one conventional commit before drafting a PR.

If the caller already created the scoped commit (for example,
`implement-agent-specs`), verify the branch is clean for that scope and do not
create a duplicate or empty commit. If a formatter leaves new tracked changes,
commit those changes before continuing. Do not reimplement the commit-message
or staging workflow inline.

### 5. Branch Sync with the Base Branch

**CRITICAL:** Before PR-body generation, sync the current branch with its base
branch (`PR_BASE` in update mode, otherwise `main`) using the
`/agentdev:update-branch` skill.

The AI agent **MUST** invoke and follow the `/agentdev:update-branch` skill instead of
re-implementing merge logic inline.

If `update-branch` reports unresolved conflicts or requires user input, stop
PR creation and ask the user to resolve or confirm conflict decisions first.

### 6. Post-sync Formatter and Commit Check

Branch synchronization can introduce formatter changes. Run the required
`local-reformat` workflow once more after `update-branch`. If it changes
tracked files, invoke `git-commit` to make one focused formatting commit. Do
not continue with formatter edits left uncommitted.

### 7. Optional Issue Linking

Issue linking is recommended but not required.

**How to find an issue number when available:**

1. Search conversation history for explicit issue references:
   - "for issue #42"
   - "closes #15"
   - "related to #23"
   - GitHub issue URLs containing issue numbers

2. If no issue number is found in conversation:
   - Check if there are recent issues that match this work:
     - Use `github/list_issues` with repository `owner` and `repo`
     - Start with `state: open`, `perPage: 10`
     - If needed, broaden query with `state: all`

- Ask the user if they want to link an issue: "Would you like to link an issue to this PR?"

3. If no issue is provided:

- Continue PR creation without issue linking
- Use a concise title without issue prefix

In update mode, preserve the existing title's issue prefix (for example `[#42]`)
rather than re-deriving the link.

### 8. PR Draft Construction

**CRITICAL:** Run this only after the branch is synchronized and clean, so the
description reflects the final changes the PR will contain.

Generate the PR description by following the
[pr-gen-description](../pr-gen-description/) skill. That skill performs the
change review; do not review the diff separately here. Give it the base branch
to compare against — `origin/${PR_BASE}` in update mode, `origin/main` in create
mode — and expect it to report any uncommitted working-tree changes as out of PR
scope rather than folding them into the body.

Use the generated output as the PR body, and use one of these title formats:

- If issue is available: `[#issue-number] Brief description`
- If issue is not available: `Brief description`
- Keep the title description concise and outcome-focused

In update mode, keep `PR_TITLE` unchanged when it still describes the branch
accurately — an update should not churn a good title.

### 9. Proceed Without Confirmation

Do **not** pause to ask the user to approve the draft. Once the title and body
are generated, continue directly to the branch push and PR creation or update.
If any later operation changes the branch diff, regenerate the title and body
through `pr-gen-description` first.

- Do not present the draft and wait for a "yes" before creating or updating the PR
- Still stop and surface the issue to the user only when a blocking error
  occurs (e.g. push divergence or a failed PR creation) — these require user
  input to resolve
- Afterwards, report the resulting PR URL/number

### 10. Push the Branch

**CRITICAL:** Before creating or updating the PR, push the branch so the remote
head ref contains every commit the body describes.

Run the bundled helper:

```bash
${CLAUDE_SKILL_DIR}/scripts/push-branch.sh
```

The script handles these cases:

- no upstream branch: pushes with `-u <remote> <branch>` using the configured `--remote` value or the default remote
- local branch ahead of upstream: pushes changes to the configured upstream
- branch up to date: exits `0` without pushing
- branch behind its upstream: exits `3` with fast-forward recovery instructions
- branch diverged from upstream: exits `3` with merge-based recovery instructions
- `--remote` conflicts with the configured upstream remote: exits `2` so the user can reconcile the remote selection
- current branch is `main` or `master`: exits `5` without pushing

Use `--remote <name>` or `--branch <name>` when the default remote or branch should be overridden.

If the script exits non-zero, display its actionable error output and abort.
Never force-push, and never update the branch ref through a GitHub API or MCP
tool — reconcile locally with `/agentdev:update-branch` and rerun this step.

### 11. Create or Update the Pull Request

In **update mode**, edit the existing PR in place with `gh`. Write the body to a
file under `./.tmp/` (relative to the repository root; create the directory if
missing) so shell quoting cannot corrupt Markdown:

```bash
gh pr edit <PR_NUMBER> --title "<new title>" --body-file ./.tmp/pr-body.md
```

Pass `--title` only when the title actually changed. Leave draft state, base
branch, labels, reviewers, and assignees untouched — an update changes text
only. Report the PR URL, and state whether the title changed, whether the body
changed, and whether the push moved the head ref.

In **create mode**, create the PR using `github/create_pull_request`.

Use the tool with these fields:

- `owner` (required): repository owner
- `repo` (required): repository name
- `title` (required): full PR title
- `head` (required): source branch name
- `base` (required): target branch (usually `main`)
- `body` (optional): PR body (include Summary, Changes, Testing, optional Related section)
- `draft` (optional): set to `true` for draft PR
- `maintainer_can_modify` (optional): set per repository policy

**Important:**

- The body should be the generated markdown from the
  [pr-gen-description](../pr-gen-description/) skill
- Do not duplicate or re-interpret the prompt's section requirements here
- If `base` is not explicitly provided by user/repo policy, set `base: main`.
- After successful creation, display the PR URL/number returned by the MCP tool
- Confirm: "Pull request created successfully: [URL]"

**Optional parameters:**

- Set `draft: true` if the user wants to create a draft PR
- Set `base: <branch>` if targeting a different base branch

### 12. Error Handling

Handle common error scenarios gracefully:

**Issue number not found:**

```
No related issue number found.
Proceeding without issue linking.
```

**No git changes:**

```
Cannot create PR: No changes detected in the working directory.
Please make and commit your changes first.
```

**GitHub MCP authentication/authorization failure:**

```
GitHub MCP request failed due to authentication or missing permissions.
Please verify MCP server authentication and token scopes (typically `repo`).
```

**Not on a feature branch** (`find-branch-pr.sh` or `push-branch.sh` exits `5`):

```
Cannot continue: you're on the main/master branch.
A pull request head must be a feature branch.

Create one with:
  git checkout -b feature/your-feature-name

Then rerun this skill.
```

**Multiple pull requests share the branch** (`find-branch-pr.sh` exits `4`):

```
Found several pull requests with this head branch.
Tell me which PR number to update; I will not guess.
```

**No conversation context:**

```
I don't have enough context to create a PR. Could you please provide:
- What changes were made?
- What was tested?
```

**PR creation failed:**

```
Failed to create pull request: [error message]
Please check GitHub MCP connectivity, authentication, and required tool permissions.
```

**Merge conflict while syncing with `origin/main`:**

```
Cannot continue PR creation: merge conflicts occurred while merging origin/main.
Please resolve conflicts, commit the merge, and retry PR creation.
```

## Ownership

The AI agent **SHALL NOT** claim authorship or co-authorship of the pull request.
The PR is created on behalf of the user, who is **FULLY** responsible for its content.

Do not add any "Created by AI" or similar attributions to the PR body unless
explicitly requested by the user.

## PR Body Guidance

For complete PR-description instructions and examples, use the
[pr-gen-description](../pr-gen-description/) skill.
