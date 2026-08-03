---
name: pr-sync
description: 'Refresh an existing GitHub pull request title and body so they match the current branch, then push the branch. Use when asked to sync, update, refresh, or regenerate a PR description or title for the branch in the working tree, including after new commits land on it'
---

# Sync PR Description

Invoke /agentdev:pr-open with additional instructions to update the PR title and body to match the current branch, then push the branch. If PR doesn't exist, it will be created.
