---
name: extract-github-actions-logs
description: 'Extract logs from a GitHub Actions run or job with the GitHub CLI. Use when asked to fetch failing CI logs, inspect a GitHub Actions run, or pull logs from a run or job URL. Keywords: github actions logs, failing ci logs, workflow run logs, job logs, gh run view.'
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/*)
---

# Extract GitHub Actions Logs

Use this skill to pull GitHub Actions logs with `gh`.

## When to Use This Skill

- Fetch logs for a failing GitHub Actions run or job
- Inspect CI from a GitHub Actions URL
- Pull the log for a specific run ID or job ID

## Prerequisites

- `gh` must be installed
- `gh` authentication is required

Use the bundled helper script to parse GitHub Actions URLs:

- [parse-actions-url.sh](./scripts/parse-actions-url.sh)

Always verify authentication first:

```bash
gh auth status
```

If that command fails or shows no authenticated account, stop immediately and tell the user to authenticate first with:

```bash
gh auth login
```

Do not continue until `gh auth status` succeeds.

## Workflow

1. Verify `gh` authentication with `gh auth status`.
2. If the user provides a GitHub Actions URL, parse it with the helper script.
3. Identify the repository, run ID, and optional job ID from the helper's shell-safe `REPO=`, `RUN_ID=`, and `JOB_ID=` output.
4. Fetch logs with `gh`.

Use these commands:

```bash
gh run view <run-id> --repo <owner>/<repo>
gh run view <run-id> --repo <owner>/<repo> --log
gh run view <run-id> --repo <owner>/<repo> --job <job-id> --log
```

Use the helper script when the input is a GitHub Actions URL:

```bash
${CLAUDE_SKILL_DIR}/scripts/parse-actions-url.sh --url '<github-actions-url>'
${CLAUDE_SKILL_DIR}/scripts/parse-actions-url.sh --url '<github-actions-url>' --format command --log
```

If the URL is a run URL, fetch the whole run log.

If the URL is a job URL, fetch the job log.

If the user wants only the failure lines, filter the job log:

```bash
gh run view <run-id> --repo <owner>/<repo> --job <job-id> --log | grep -nE "FAILED|FAILURES|AssertionError|ERROR:|Segmentation fault|test_"
```

Or generate that command from the helper script:

```bash
${CLAUDE_SKILL_DIR}/scripts/parse-actions-url.sh --url '<github-actions-job-url>' --format command --log --grep-failures
```

If the user needs artifacts the run uploaded (test reports, coverage, build logs), download them with `gh run download`.

Discover the exact artifact names for a run first — they are workflow-specific:

```bash
gh api repos/<owner>/<repo>/actions/runs/<run-id>/artifacts --jq '.artifacts[].name'
```

Then download one, or several at once:

```bash
gh run download <run-id> --repo <owner>/<repo> -n <artifact-name> -D ./.tmp/actions-run-<run-id>
gh run download <run-id> --repo <owner>/<repo> -n <artifact-a> -n <artifact-b> -D ./.tmp/actions-run-<run-id>
```

Omit `-n` entirely to fetch every artifact from the run.

## Example

Given this workflow run URL:

`https://github.com/<owner>/<repo>/actions/runs/12345678901`

Run:

```bash
gh auth status
${CLAUDE_SKILL_DIR}/scripts/parse-actions-url.sh --url 'https://github.com/<owner>/<repo>/actions/runs/12345678901' --format command --log
```

Then run the emitted `gh run view ... --log` command to fetch the whole run log.

To inspect and download the artifacts for the same run:

```bash
gh api repos/<owner>/<repo>/actions/runs/12345678901/artifacts --jq '.artifacts[].name'
gh run download 12345678901 --repo <owner>/<repo> -n <artifact-name> -D ./.tmp/actions-run-12345678901
```

When a workflow builds a matrix, artifact names usually carry the matrix value
(for example an `-amd64` / `-arm64` suffix). Pick the one matching the failing
job rather than guessing.

Given this failing CI job URL:

`https://github.com/<owner>/<repo>/actions/runs/12345678901/job/23456789012?pr=42`

Extract:

- repo: `<owner>/<repo>`
- run ID: `12345678901`
- job ID: `23456789012`

Then run:

```bash
gh auth status
gh run view 12345678901 --repo <owner>/<repo> --job 23456789012 --log
```

Or, to focus on the likely failure lines:

```bash
gh run view 12345678901 --repo <owner>/<repo> --job 23456789012 --log | grep -nE "FAILED|FAILURES|AssertionError|ERROR:|Segmentation fault|test_" | tail -n 200
```

The same job URL can be parsed with:

```bash
${CLAUDE_SKILL_DIR}/scripts/parse-actions-url.sh --url 'https://github.com/<owner>/<repo>/actions/runs/12345678901/job/23456789012?pr=42'
```
