---
name: python-format-lint
description: 'Format and lint Python in this repository with ruff — format and autofix first, then verify with the non-mutating check that CI gates on. Use when formatting Python, fixing style/lint violations, organizing imports, or checking why a lint job fails in CI. Keywords: ruff, format, lint, isort, style, E501, I001, noqa, python-reformat, python-lint-check.'
---

# Python Format & Lint (ruff)

This repository uses **ruff** for both formatting and linting, configured by
[ruff.toml](../../../ruff.toml) (line-length 99, single quotes, isort with
`force-sort-within-sections`). Two scripts wrap it, and the order matters:
**`python-reformat.sh` mutates, `python-lint-check.sh` is the gate CI enforces.**

Never judge compliance with stock `flake8` or `black` — their defaults (79-char
limit, double quotes, different isort grouping) produce false positives that do
not match this repo and do not fail CI.

## When to Use This Skill

- Formatting or cleaning up Python after editing source or tests
- A lint job fails in CI and you need to reproduce and fix it locally
- Organizing imports, fixing line length, or resolving import-group errors
- Deciding whether a `# noqa` is justified

## Workflow

1. **Format and autofix with ruff.** Run the bundled reformat script from the
   repo root — it runs `ruff format`, `ruff check --fix`, and isort across the
   repo's Python sources and scripts. Ansible and the non-Python formats are
   owned by Super-Linter; use the [local-reformat](../local-reformat/SKILL.md)
   skill for that workflow:

   ```bash
   scripts/python-reformat.sh
   ```

   For a tighter loop on specific files, invoke ruff directly (config is picked
   up automatically):

   ```bash
   .venv/bin/ruff format path/to/file.py
   .venv/bin/ruff check --fix path/to/file.py
   ```

2. **Verify with the check script.** It runs `ruff format --check` and
   `ruff check` without mutating anything. With no arguments it checks the
   repo's Python sources; pass explicit paths to scope it for speed:

   ```bash
   scripts/python-lint-check.sh                        # everything
   scripts/python-lint-check.sh py_packages/validate_agent_files
   scripts/python-lint-check.sh path/to/file.py        # one file
   ```

3. **Fix remaining violations by hand.** Anything the check reports that
   `ruff check --fix` did not autofix must be fixed in the source. Use a
   targeted `# noqa: <rule>` **only** for a formatter-required incompatibility
   (e.g. `E203` on a slice); never disable a rule for a whole file or package.
   For import-group mismatches, adjust `lint.isort` in
   [ruff.toml](../../../ruff.toml) rather than sprinkling `noqa`.

4. **Confirm clean.** Re-run step 2 until it exits zero with no output.

## Scripts

| Script                                                        | Purpose                                                                     |
| ------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [python-reformat.sh](../../../scripts/python-reformat.sh)     | `ruff format` + `ruff check --fix` + isort across Python sources and scripts |
| [python-lint-check.sh](../../../scripts/python-lint-check.sh) | Non-mutating `ruff format --check` + `ruff check` (the CI gate)              |

## Troubleshooting

| Symptom                                                    | Cause                                        | Fix                                                                        |
| ---------------------------------------------------------- | -------------------------------------------- | -------------------------------------------------------------------------- |
| `flake8` locally flags `E501` at 79 chars but CI is green   | You ran stock `flake8`, not ruff              | Use `scripts/python-lint-check.sh`; the repo limit is 99                    |
| Formatter keeps fighting your import order                  | isort settings live in `ruff.toml`            | Adjust `lint.isort` there, then re-run `python-reformat.sh`                 |
| `ruff: command not found`                                   | The uv environment is not synced              | Run `scripts/uv-sync.sh` (or `uv sync`); the scripts activate `.venv`       |
| Reformat script rewrote files you did not touch             | It formats whole directories, not the diff    | Commit your change first, then reformat, so the two are separate commits    |

## References

- Python coding conventions: [AGENTS.md](../../../AGENTS.md) (Python section)
- ruff configuration: [ruff.toml](../../../ruff.toml)
