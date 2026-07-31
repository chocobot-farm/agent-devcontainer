# 01 — Base image and catalog version pinning

Resolves **F8**. Independent of the other specs; schedule it first.

## Goal

A repository that consumes `ghcr.io/chocobot-farm/agent-desktop` must be told,
by an automated pull request, when that image moves. Today nothing does, so a
consumer silently runs a stale environment for as long as its pin is not touched
by hand.

This spec establishes the pinning convention and the Renovate rules that keep it
current, in this repository and in every consumer.

## Why first

Every mechanism in this spike's plan — the image, the plugin, the seed — is a
version pin held by someone else. Without an update path they all rot the same
way. A migration to plugin distribution without a bump trigger is worse than no
migration, because it converts one stale copy into N stale pins that nobody is
watching.

## Prerequisites

None.

## Implementation

### 1. Pin by digest, not by tag

`.devcontainer/docker-compose.yml:53` currently reads:

```yaml
image: ghcr.io/chocobot-farm/agent-desktop:edge
```

`:edge` is a moving tag: the container silently changes under the developer on
every `docker compose pull`, and there is no artifact for Renovate to bump.
Replace it with a tag-plus-digest pin, which is reproducible and is the form
Renovate understands:

```yaml
image: ghcr.io/chocobot-farm/agent-desktop:edge@sha256:<digest>
```

Apply the same treatment to `docker/desktop/agent-desktop.dockerfile:1`, whose
`ARG FROM_IMAGE` default pins `ubuntu-ansible:edge`.

Keep the human-readable tag alongside the digest. Renovate rewrites both and the
tag is what makes a diff reviewable.

### 2. Add a Renovate configuration

This repository has neither `renovate.json` nor `dependabot.yml` today. Add
`.github/renovate.json` covering:

- `docker-compose` and `dockerfile` managers, for the two pins above.
- `github-actions`, for the pinned action refs already in
  `.github/actions/**` and `.github/workflows/**`.
- A `customManager` for the plugin version in `extraKnownMarketplaces`, added by
  spec `02`. Until `02` lands this section is inert; add it then, not now.

Group the two GHCR images into a single pull request. They are built from one
pipeline and a split bump produces a mismatched pair.

### 3. Document the consumer contract

The README's "Using it in another project" section shows `:edge` in both
options. Update both to the digest form, and add a short subsection stating that
a consumer is expected to run Renovate (or equivalent) against the pin, with the
minimal configuration inline.

This is the part that actually propagates: the convention only holds if the
copy-paste starting point already has it.

## Acceptance criteria

- No `agent-desktop` or `ubuntu-ansible` reference in the repository resolves to
  a bare moving tag.
- `.github/renovate.json` exists, is valid, and its dry run proposes an update
  when either GHCR image advances.
- Both GHCR image bumps arrive as one pull request, not two.
- The README's consumer instructions show the digest form and state the update
  expectation.

## Test plan

- `npx --yes renovate-config-validator .github/renovate.json` passes.
- A Renovate dry run against the repository lists both image pins as detected
  dependencies and produces a single grouped branch for them.
- `docker compose -f .devcontainer/docker-compose.yml config` resolves, and the
  devcontainer starts from the digest-pinned image.
- Publish a new `edge` build, then confirm the next Renovate run opens a bump
  pull request rather than the pin advancing on its own.

## Notes

The Dr.QP spike raised this as its F7 and called it "the main argument against
migrating". Treat a failure here as blocking for `02` and `03`, not as a
follow-up.
