# Template reuse validation — raw findings

Both reuse workflows in `docs/using-as-template.md` were executed end to end rather than
reasoned about, to check that the confirmed publisher-deletion set actually produces a
working consuming repository.

**Deletion set under test** (confirmed as the full-copy boundary): `.agents/`,
`.claude-plugin/`, `py_packages/validate_agent_files/`,
`scripts/validate-super-linter-tool-versions.sh`, `docs/agents/specs/`.

## What was run

**Workflow A — full copy.** A tree containing only the retained files was materialized from
`git ls-files` minus the deletion set and the optional image bundle, then edited per the
guide (`pyproject.toml`, `.pre-commit-config.yaml`, `.ruff.toml`, `devcontainer.json`,
`.claude/settings.json`, `primary-checks.yml`, `paths-filter/action.yml`, `reformat.yml`,
`validate-agent-files.yml`).

| Check                                       | Result                                  |
| ------------------------------------------- | --------------------------------------- |
| `docker compose … config`                   | Parses.                                 |
| `uv lock` + `uv sync --all-groups`          | Succeeds.                               |
| `pre-commit run --all-files`                | All hooks pass or skip. No failures.    |
| `zizmor --persona=regular` on the workflows | No findings (2 ignored, 11 suppressed). |

**Workflow B — existing repository.** Applied to `plume-works/agent-self-improvement`, which
already carried seven of the template's linter configuration files verbatim.

| Check                        | Result                                                            |
| ---------------------------- | ----------------------------------------------------------------- |
| `devcontainer-init.sh`       | Generates a correct host-specific `.env`, workspace name and all. |
| `docker compose … config`    | Parses.                                                           |
| `pre-commit run --all-files` | Green and idempotent after the config reconciliation below.       |
| Project test suite           | 597 passed; the one failure is pre-existing (see P3).             |

A container was not started for the consuming repository, so the post-create and post-start
lifecycle remains exercised only here.

## Issues

### P1 — `agent-desktop` does not install `validate_agent_files`

The guide instructs consumers to call the "image-provided `validate_agent_files`" after
deleting `py_packages/validate_agent_files/`. Nothing under `ansible/` or `docker/`
references the package, and the command is not on `PATH` in a running container:

```console
$ grep -rni "validate.agent\|validate_agent" ansible/ docker/
$ command -v validate_agent_files
```

Both return nothing. In this repository the command resolves only through `uv run`, from the
editable source that a full template copy deletes.

The documented direction is correct and stays as written — installing the package into the
image is the follow-up work that makes it true. Until that lands, a consumer following the
guide has no validator. Tracked separately; see `0001-ship-validator-in-image.md`.

### P2 — `.ruff.toml` silently disables a project's `[tool.ruff]` block

Ruff resolves the first configuration file it finds and stops. A repository that adopts the
template's root `.ruff.toml` while configuring ruff under `[tool.ruff]` in `pyproject.toml`
loses the entire pyproject block with no warning.

Observed live in `agent-self-improvement`: its `target-version = "py39"` (matching a 3.9
runtime floor), `line-length = 100`, and its `UP` ignores had never taken effect. It was
being linted as `py312` against the publisher's rule set, including
`known-first-party = ["validate_agent_files", "mock_catalog"]` — so its own `selfimprove`
package was sorted as a third-party import.

`ruff check --show-settings <path>` prints the resolved `Settings path:` and is the fastest
way to see which file won. Now documented in the guide's Workflow B step 3.

### P3 — pre-existing test failure in `agent-self-improvement`, unrelated to adoption

`tests/integration/test_dispatcher.py::test_self_test_fails_when_state_root_is_unwritable`
fails when the suite runs as root, because root can write into the `0o500` directory the test
uses to simulate an unwritable state root. Confirmed on an unmodified checkout. Not caused by
and not addressed by template adoption; raised for that repository to own.

### P4 — formatter adoption rewrites verbatim third-party captures

Adding the template's Prettier and ruff hooks to a repository reformats everything they can
reach. In `agent-self-improvement` that included `docs/case-study/hermes/prompts/` (a
snapshot with a stated exactness contract) and
`docs/case-study/scrapeshq-memory-plan/source/` (a capture whose README records SHA-256
digests of the files). Both needed `.prettierignore` and ruff `extend-exclude` entries before
the first hook run. Now documented in the guide's Workflow B step 3.

### P5 — `reformat.yml`'s catalog dependency was under-specified

The guide said to "replace repository-relative catalog helper paths with commands available
in the chosen CI environment", which understates the only real blocker: two steps call
`./.agents/plugins/agentdev/bin/super-linter-env.sh`, which the full-copy deletion removes.
The script emits nothing but `NAME=value` lines, so both blocks inline into the workflow
directly. Now stated concretely in the guide's step 8.

### P6 — smaller gaps in the documented edits

All folded into the guide:

- deleting `scripts/validate-super-linter-tool-versions.sh` empties `scripts/`, and deleting
  `py_packages/validate_agent_files/` leaves a standalone `LICENSE` behind;
- `pyproject.toml` step missed `toml`, `pydantic`, and `python-frontmatter`, which exist for
  the validator package, and did not say what to do when `testpaths` empties out;
- removing the `ci` job from `primary-checks.yml` orphans the `clean_build`
  `workflow_dispatch` input;
- the `zizmor` pre-commit hook is `language: system` and needs `zizmor` on `PATH`, which does
  not hold outside the development image. `zizmorcore/zizmor-pre-commit` pinned by revision
  works anywhere and was verified in `agent-self-improvement`;
- Workflow B never said to add `.devcontainer/.env` and `.devcontainer/local.env` to an
  existing `.gitignore`, so the generated host-specific env file lands in the next commit;
  and
- `--require-marketplace claude codex` asserts publisher manifests a consumer does not have.

## Stale references found in this repository

Neither affects the template boundary; both are publisher-side and pre-existing.

- `.github/workflows/reformat.yml` filters on
  `.github/workflows/validate-super-linter-tool-versions.yml`, which does not exist.
- The same filter lists `.github/super-linter-*.env`; no such files exist.
