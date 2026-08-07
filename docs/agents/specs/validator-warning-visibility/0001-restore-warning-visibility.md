# 0001 — Restore warning and recommendation visibility

Status: Not started.

## Problem

`validate_agent_files` advertises a recommendation mode (`--recommend`) and two ways to
suppress warnings (`--no-warnings`, `--errors-only`). None of them changes any output. Three
breaks on the same path, detailed as P1-P3 in this folder's `README.md`:

1. the only two validators that honor `show_warnings` are never invoked by the engine;
2. `--no-warnings` writes `args.warnings` while `main.py` reads `args.no_warnings`; and
3. `CrossReferenceValidator` stores `show_warnings` and never reads it.

Contributors and CI are told to run `--recommend` by `README.md` and
`.github/workflows/validate-agent-files.yml`. It is currently a no-op, so the repository
believes it has a quality signal that it does not have.

## Scope

Decide what the recommendation set should be, then make the flags reach it.

Fixing P2 alone is not worth shipping: correcting the attribute name makes `--no-warnings`
control a value that still reaches nothing. Fix the wiring first, or fix all three together.

The first decision belongs in this spec, not in the code review of the change:

- **Restore** — wire `SkillFrontmatterValidator` and `SkillStructureValidator` into
  `CustomizationsValidationEngine` and treat their existing checks as the intended
  recommendation set. Cheapest, and the tests in `tests/test_skill_validation.py` already
  describe the behavior.
- **Redesign** — treat the two orphaned validators as abandoned and define the
  recommendation set deliberately. More work, and it should not happen without a reason to
  distrust the existing checks.

Trace the git history of `validators/skill.py` and `core.py` before choosing; whether these
call sites were dropped or never existed is the deciding evidence and was not investigated.

## Acceptance criteria

1. A skill that triggers a recommendation check reports it under `--recommend` and does not
   report it without the flag. A regression test asserts both directions against a fixture,
   not against repository content.
2. `--no-warnings` suppresses warning-level issues, in each of the `text`, `json`, and `csv`
   formatters.
3. Warning-level issues never change the exit code. It stays error-driven, as
   `ValidationResult.is_valid` defines it. A test pins this: a fixture with warnings and no
   errors exits 0 with and without `--recommend`.
4. `main.py` reads the real argparse destinations. No `getattr(parsed_args, ...)` with a
   default on a flag the parser always defines — those defaults are what let P2 pass
   silently, and they will hide the next rename the same way.
5. `CrossReferenceValidator` either uses `show_warnings` or stops accepting it. No stored
   and unread field survives the change.
6. The redundancy between `--no-warnings` and `--errors-only` is resolved: either they are
   documented as meaningfully different, or one is removed.

## Constraints

- Per `py_packages/validate_agent_files/AGENTS.md`: tests reference no path outside the
  package root, import flag names and other contract values from the code under test rather
  than restating them as literals, and use invented identities in fixtures.
- CLI and library behavior tests belong in `py_packages/validate_agent_files/tests/`, not in
  the plugin suite.
- Turning recommendations on for the first time will surface findings across
  `.agents/plugins/agentdev/`. Expect that and triage it; do not weaken the checks to keep
  the tree green, and do not fold catalog edits into this change.
- `.github/workflows/validate-agent-files.yml` runs `--recommend` today. Confirm the job
  still passes, or split the catalog cleanup into its own commit ahead of the fix.

## Out of scope

- The image bundling in `docs/agents/specs/template-reuse-validation/`. Independent; either
  can land first.
- Adding new validators. This restores a path, it does not extend the rule set.

## Verification

```bash
cd py_packages/validate_agent_files && uv run --isolated --extra dev pytest
```

Then, from the repository root, against a scratch fixture under `.tmp/` — a skill whose
description carries the vague terms the frontmatter validator looks for:

```bash
uv run validate_agent_files .tmp/<fixture>              # no recommendations
uv run validate_agent_files --recommend .tmp/<fixture>  # recommendations, exit code unchanged
uv run validate_agent_files --recommend --no-warnings .tmp/<fixture>  # suppressed again
```

The first and third must match. The second must differ from both. Today all three are
identical, which is the bug.

Finally, run the publisher gate the repository actually depends on:

```bash
uv run validate_agent_files --recommend . --require-marketplace claude codex
```
