# Agents Guidelines

NEVER use "$TMPDIR" env variable.
ALWAYS use "./.tmp" (relative to the repo root) for temporary files; create it if it does not exist.
NEVER use GitHub API or GitHub MCP tools to update branch refs or push branch contents. Use local git branch workflows instead; if push authentication is unavailable, stop and report the blocker rather than updating the branch remotely via API.

## Best Practices for Agents

0. NEVER change git config on local or global level unless explicitly instructed. NEVER switch/change remote.
1. **Use `uv` for Python and `bun` for JavaScript.** Run project commands through `uv run`; sync with `scripts/devcontainer-uv-sync.sh` (or `uv sync`) after changing dependencies. Never install packages globally.
2. **Scope test runs narrowly** while iterating: `uv run pytest <path>::<test_name>`, `bun test <path>`. Run the full suite only when asked.
3. **Escalate to a container when the host lacks the toolchain — never give up after a local failure.** If `uv` or `bun` is missing, or a command needs the provisioned image, escalate in this order: (a) Docker daemon available → use the `/agentdev:microvm-sandbox` skill to run the command through `devcontainer exec`; (b) no Docker daemon → use the `/agentdev:remote-codespace-session` skill to run it on a GitHub Codespace over SSH. Only report a blocker if both escalation paths are unavailable (e.g. no `gh` auth).
4. **For yes/no and multiple-choice questions, prefer the assistant's structured-question tool** over free-text (VS Code Copilot: `vscode/askQuestions`; Claude Code: `AskUserQuestion`).
5. **Validate the agent catalog after editing it**: `uv run validate_agent_files --recommend . --require-marketplace claude codex`.
6. **Ansible changes** must pass `(cd ansible && uv run ansible-lint .)` and `(cd ansible && uv run ansible-playbook --syntax-check playbooks/setup-dev.yml)`. The real gate is a local image build — see the README.

### When in Doubt

Consult the **[Principal Engineer](/.agents/plugins/agentdev/agents/principal-engineer.agent.md)** agent for architecture, design decisions, and implementation strategies.

## Coding Conventions

### Python

- Follow **PEP 8**: 4 spaces per indentation level, descriptive names. The line limit is **99** (`.ruff.toml`), not 79.
- Use type hints (PEP 484, `typing` module) and PEP 257 docstrings placed immediately after `def`/`class`
- Formatting and autofixes are applied by **ruff**, via the pre-commit hooks locally and Super-Linter in CI (`super-linter-local.sh`, from the plugin `bin/`, reproduces the CI pass). Verify with `python-lint-check.sh` for a fast, Docker-free check. Never judge style with stock `flake8` or `black`: their defaults (79-char limit, double quotes, different isort grouping) produce false positives that do not match this repo and do not fail CI. Full workflow in the `/agentdev:python-format-lint` skill
- **Exception handling**: never write empty handlers (`except ...: pass`). Handle expected exceptions explicitly by at least one of: logging context, returning a safe fallback value, re-raising with context, or raising `SystemExit` for CLI interruption paths (`raise SystemExit(130)` for user interrupts). If an exception must be intentionally ignored, document the reason in a comment and keep the ignored scope minimal. Prefer specific exception types over broad `except Exception`

### Python Testing

- **Always use `pytest`** — never `unittest`
- Prefer multiple smaller, focused test files over large monolithic ones
- **Tests must not depend on this repository's own identity.** Build fixtures from mock data — a made-up marketplace name, plugin name, org, and paths — never the real values from `marketplace.json`, `plugin.json`, or a shipped catalog directory. A rename of something this repository publishes must never require a test edit; if it does, the test was asserting identity instead of behavior
- **Keep the mock data in one shared module per test package** (for `validate_agent_files`, `tests/mock_catalog.py`) and import the constants and builders from it, so a fixture change lands in one file. Add the module to `known-first-party` in `.ruff.toml` so import sorting groups it with the package under test
- Values that belong to the _contract_ rather than to an identity — well-known manifest locations, CLI flags, the package's own entry points — should be imported from the code under test instead of restated as literals, so a contract change fails loudly in one place

### Shell

- All scripts are `#!/usr/bin/env bash` with `set -euo pipefail`, and must pass `shellcheck` (enforced by pre-commit and Super-Linter)
- Quote every expansion; prefer `"${var:-default}"` over assuming a variable is set

### C++

- Follow the C++ Core Guidelines with modern C++ (C++17 or later): RAII for resource management, value semantics by default, smart pointers instead of raw pointers, standard library containers and algorithms
- Make ownership explicit in API design; focus on correctness first, then optimize with evidence
- Formatting is `clang-format` per [.clang-format](.clang-format)

### Ansible

- One responsibility per role. Prefix role variables with the role name (`dev_tools_*`, `agentic_tools_*`); the shared facts `workspace_folder`, `user_home`, and `dev_user` are the documented exceptions
- Roles must be independently runnable. Do not rely on a `register:` from another role without tolerating it being undefined
- Pin every external download with a version **and** a per-architecture checksum, as `dev_tools` does for `zizmor`
- Read paths that vary per consuming project from the environment at runtime (`DEV_WORKSPACE_FOLDER`) with `workspace_folder` as the fallback. Never hardcode a workspace path

## Catalog Locations

- **Claude** (canonical source of truth): the `agentdev` plugin — `.agents/plugins/agentdev/agents/`, `.agents/plugins/agentdev/skills/`, `.agents/plugins/agentdev/hooks/`, `.agents/plugins/agentdev/bin/`. Skills are namespaced: `/agentdev:<skill-name>`
- **Codex**: the same `.agents/plugins/agentdev/` tree, packaged by `.agents/plugins/agentdev/.codex-plugin/plugin.json`; Codex discovers `.agents/plugins/agentdev/agents/` and `.agents/plugins/agentdev/skills/` directly
- **This repository's own config**: `.claude/settings.json` only; it enables the plugin from the marketplace declared in `.claude-plugin/marketplace.json`. `settings.json` is strict JSON — no comments, no trailing commas

Update `.agents/plugins/agentdev/` sources directly. Never write a repository-relative catalog path inside the plugin — use `${CLAUDE_SKILL_DIR}/...` for a path within a skill and a namespaced invocation for a sibling skill. No link inside the plugin may resolve outside the plugin root: the catalog ships to the plugin cache of whatever repository enables it, so a `../../../../../AGENTS.md` link silently supplies this repository's conventions to a consumer instead of theirs. Describe per-repository files (`AGENTS.md`, lint configuration, the pull request template) in prose so they are resolved at runtime; the validator enforces this across every markdown file a plugin ships, including `references/` pages and the plugin README, for Claude and Codex packages alike. Keep the Claude and Codex plugin manifest versions aligned when releasing the shared catalog.

**Edit `AGENTS.md`; `CLAUDE.md` only includes it (`@AGENTS.md`), so changes there cover all agents.**

## Spikes

When doing investigation work aka spikes document your findings in specs under `docs/agents/specs/<spike-topic>` in a structured way, create new subfolder `<spike-topic>` for the subject of investigation. Create `README.md` with raw findings, including list of issues with assigned priorities. Create a series of spec files with implementation guidance.
