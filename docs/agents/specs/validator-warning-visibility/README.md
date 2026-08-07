# Validator warning visibility — raw findings

Found while reading `validate_agent_files` for the image-bundling work
(`docs/agents/specs/template-reuse-validation/0001-ship-validator-in-image.md`). Nothing
here is caused by that change, and nothing here was fixed by it.

The short version: the validator's entire warning-and-recommendation path is inert. Three
independent breaks sit on the same wire, so `--recommend`, `--no-warnings`, and the
`show_warnings` plumbing behind them have no observable effect on any run.

## How this was checked

Static: `grep -rn "show_warnings"` across `py_packages/validate_agent_files/`, and a read of
every reader and writer it returns.

Observed: a scratch skill carrying three of the vague description terms
`SkillFrontmatterValidator` looks for (`helpers`, `utilities`, `tools`) was validated with
and without `--recommend`. Output was byte-identical, and the summary line read
`Errors: 1, Warnings: 0` both times. The same comparison for
`--recommend` against `--recommend --no-warnings` over
`.agents/plugins/agentdev/skills` was also byte-identical.

## Issues

### P1 — `--recommend` cannot produce recommendations

`show_warnings` is read in exactly two places:
`SkillFrontmatterValidator.validate` (`validators/skill.py:91`, the vague-description check)
and `SkillStructureValidator.validate` (`validators/skill.py:150`, the section-content
check). Neither class is imported anywhere in the package outside its own module —
`grep -rn "SkillFrontmatterValidator\|SkillStructureValidator"` returns only
`validators/skill.py` and `tests/test_skill_validation.py`.

So the two validators that honor the flag are never reached by the engine, and the tests
that cover them construct them directly. `--recommend` is documented as "Show
recommendations for improvement" and is what `.github/workflows/validate-agent-files.yml`
and `README.md` tell contributors to run. It shows nothing extra.

This is the load-bearing one: it is not a flag that fails to disable output, it is a feature
that produces none.

### P2 — `--no-warnings` writes an attribute nothing reads

`cli.py:65-71` declares the flag as `action='store_false', dest='warnings', default=True`, so
argparse sets `args.warnings`. `main.py:23` reads
`getattr(parsed_args, 'no_warnings', False)` — an attribute the parser never creates. The
`getattr` default swallows the mismatch, so the branch is permanently `False` and the flag
is dead.

`--errors-only` on the same line is read correctly (`dest` defaults to `errors_only`), so it
is the only flag that reaches `show_warnings` at all — which, per P1 and P3, still changes
nothing downstream.

Worth settling alongside the fix: the two flags are documented as doing the same thing —
`'Exclude warnings from validation results'` versus `'Show only errors, exclude warnings'`.
One of them is redundant.

### P3 — `CrossReferenceValidator` stores `show_warnings` and never reads it

`core.py:98` passes `show_warnings` into `CrossReferenceValidator`, which assigns
`self.show_warnings` at `validators/cross_reference.py:44` and never consults it again. This
is the only path by which `show_warnings` currently leaves the engine, and it terminates in
a dead field.

## Not investigated

Whether the intended design was for these validators to be wired in and later dropped, or
never wired in at all. The git history was not traced. That question decides whether the fix
is "restore the call sites" or "design the recommendation set from scratch", and
`0001-restore-warning-visibility.md` leaves it open deliberately.
