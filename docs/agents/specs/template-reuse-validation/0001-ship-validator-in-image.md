# 0001 — Install `validate_agent_files` into `agent-desktop`

Status: Not started.

## Problem

`docs/using-as-template.md` and `docs/repository-structure.md` both instruct a consuming
project to delete `py_packages/validate_agent_files/` and call the command supplied by the
`agent-desktop` image. The image does not supply it.

`grep -rni "validate.agent\|validate_agent" ansible/ docker/` returns nothing, and
`validate_agent_files` is not on `PATH` in a running container. The command resolves in this
repository only through `uv run`, from the editable path dependency in `[tool.uv.sources]`
that the documented deletion removes.

The consequence is narrow but total: a consumer that follows the full-copy workflow and wants
agent-file validation has no validator, in the devcontainer or in CI.

## Scope

Make the documented assumption true. The guide's wording does not change.

## Acceptance criteria

1. `command -v validate_agent_files` resolves inside a container started from the published
   image, for the non-root user the devcontainer runs as.
2. `validate_agent_files --help` exits 0 there without a `uv run` prefix and without the
   repository checked out.
3. The version installed into the image is pinned and updated deliberately, the same way the
   catalog version is pinned by `AGENTDEV_PLUGIN_VERSION`.
4. A CI job running in the digest-pinned image can validate a consuming repository's agent
   files, as `docs/using-as-template.md` describes under "Agent-file validation".
5. The image build does not depend on the consuming repository's checkout — the package is
   installed at build time, not staged for a lifecycle hook to install.

## Constraints

- The package currently exists only as a path dependency. It is not published to PyPI, so
  the build needs either a wheel built from the repository build context or a published
  artifact to install from. Choose one explicitly; the first keeps release coupling inside
  this repository, the second removes the build-context dependency.
- `docker/desktop/agent-desktop.Dockerfile` already reads `.claude-plugin/` and `.agents/`
  from the build context under `agentic_tools_stage_catalog=true`. Reusing that context for
  `py_packages/validate_agent_files` is consistent with the existing build, and inherits the
  same constraint recorded in `docs/agents/specs/catalog-distribution/`: it only works while
  the publisher source is present.
- Installing into the system interpreter must not collide with `uv`-managed project
  environments. Prefer an isolated install that puts a single entry point on `PATH`.
- Whatever installs it belongs in `ansible/roles/`, not in the Dockerfile, matching how every
  other tool in the image is provisioned.

## Out of scope

- Changing the validator's own CLI or behavior.
- Publishing the package to PyPI as a product decision, beyond choosing it as the install
  source if that is the simpler path.
- The publisher's own `validate-agent-files.yml` workflow, which uses the local package and
  keeps working either way.

## Verification

Build the image, then from a container started on the resulting digest with no repository
mounted:

```bash
command -v validate_agent_files
validate_agent_files --help
```

Then run the consuming-repository shape: check out a project with agent files, mount it, and
run `validate_agent_files --recommend .` without `uv run` and without a local copy of
`py_packages/`.
