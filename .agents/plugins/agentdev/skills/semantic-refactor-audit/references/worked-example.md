# Worked example: removing escaping links from a plugin catalog

A complete audit, including the reasoning that produced the exposing context and
the mistakes the procedure caught. Read this when designing the contexts for a
new audit, or when writing the probe prompt.

## The change

Skills shipped in a plugin linked to files at the publishing repository's root
with relative paths like `../../../../../AGENTS.md`. The plugin is installed by
other repositories, where those links resolve inside the plugin cache — to the
publishing repository's conventions rather than the consumer's. They do not
fail; they silently supply the wrong content.

Twenty such references were rewritten as prose ("the `AGENTS.md` at the root of
the repository being reviewed"), so the target is resolved at runtime.

## Step 1 — invariant and permitted deltas

**Invariant:** every action, command, ordering constraint, and configuration
assertion in each skill survives verbatim. Only the way a file is _referred to_
may change.

**Permitted deltas**, enumerated before editing:

1. `generate-pr-description` gains a fallback for a repository with no pull
   request template. Prose cannot assume the file exists the way a working link
   could, so this behavior had to be stated rather than inherited.
2. `create-skill` gains an authoring rule describing the new convention.

Everything else moving would be a defect. This list is what made the comparison
decidable instead of negotiable.

## Step 2 — designing the exposing context

The naive audit would have proved nothing. Run from inside the publishing
repository, `../../../../../AGENTS.md` resolves correctly _today_; a before and
after capture would be identical, and the audit would have "passed" while
telling you nothing about the defect.

The defect only appears where the plugin is installed without the surrounding
repository. So every artifact was probed in two contexts:

| Context  | Path                                | Simulates                 |
| -------- | ----------------------------------- | ------------------------- |
| in-repo  | the live catalog                    | the publishing repository |
| isolated | `./.tmp/link-audit/<phase>/plugin/` | a plugin cache or package |

The isolated context was a plain recursive copy of the plugin subtree into
`./.tmp/`. Five directory levels above a skill file there lands on a directory
that holds no `AGENTS.md`, reproducing the consumer failure without leaving the
repository.

**Verify the isolation.** The depth was checked with `realpath` before the
probes ran — an early estimate of where the links would land was off by one
directory, which would have quietly weakened the whole audit.

## Step 3 — the two axes

**Ground truth** was a shell loop over every escaping reference, resolving it
with `realpath -m` and testing existence, in both contexts, written to
`before/ground-truth.md`. This is the axis that decides facts.

**Semantic read-back** was one cheap subagent per artifact, reading both copies.
The prompt, identical in both phases apart from paths:

> Read these two copies of the same instruction file: `<path A>` and `<path B>`.
> For each copy, report strictly what the text says, never what you think it
> intends:
>
> 1. Every external file the document directs you to open, as the literal path
>    or description it gives.
> 2. For each: can you locate it from your current working directory? Give the
>    path you resolved to, or say it does not exist.
> 3. The concrete actions and rules the document imposes, as at most 10 bullets.
>
> Do not follow links out of the document. Do not edit anything.
>
> Your ONLY write action is to save your report to `<report path>`. Do not
> create, edit, or delete any other file.

Item 2 is deliberately redundant with the deterministic axis — it is what
exposed the probes' unreliability.

## Step 4 — the control

All 20 references resolved in-repo and all 20 were missing in the isolated
context. Every affected file exhibited the failure, so the premise held and no
inventory entry needed revisiting.

Had any file come back clean, that reference would not have been a real problem
and its place in the change would have needed re-checking first.

## Step 6 — the comparison

**Defect fixed:** after the change, 89 references resolved _identically_ in both
contexts. The only unresolved entries were 11 occurrences of a literal
placeholder inside pre-existing ignore markers, present in both contexts and
therefore not a difference.

**Invariant held:** judged against `git diff`, not the probe summaries. Every
hunk was a link-to-prose substitution.

**Only permitted deltas:** the template fallback and the authoring rule, both on
the list. Notably, both before-phase probes independently reported "no fallback
specified" — confirming the gap was pre-existing and that stating it was a fix,
not drift.

## What the procedure caught

**Three of fourteen probe reports were factually wrong**, in both directions:

- Two before-phase probes claimed the isolated copy resolved its references
  cleanly. Nothing resolved; `realpath` showed every one missing.
- One after-phase probe claimed a bundled script dangled in the isolated tree.
  It existed.

Had path resolution been taken from the probes, the audit would have concluded
there was no defect to fix, then that the fix had broken something. The
deterministic axis is not redundancy — it is the part that decides.

A fourth-order benefit: running the validator over the retained `before`
snapshot flagged its escaping links automatically, which confirmed the new
enforcement rule worked on real content rather than only on test fixtures.
