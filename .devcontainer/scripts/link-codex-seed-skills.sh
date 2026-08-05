#!/usr/bin/env bash
set -euo pipefail

# Point ~/.codex/skills at the catalog seeded into the image.
#
# Codex has no seed mechanism of its own; it reads personal skills from
# $CODEX_HOME/skills. The image already creates that symlink, but docker-compose.yml
# mounts the shared agentdev-codex volume over the Codex home, which shadows it.
# Re-create the link once the volume is in place.
#
# A project that is itself the catalog's source sets AGENTDEV_SEED_DIR to "" in its
# devcontainer.json and this becomes a no-op.

seed_root="${AGENTDEV_SEED_DIR:-}"
if [[ -z "$seed_root" ]]; then
    echo "AGENTDEV_SEED_DIR is empty; skipping the seeded Codex catalog link."
    exit 0
fi

seeded_skills="$seed_root/codex/skills"
if [[ ! -d "$seeded_skills" ]]; then
    echo "No seeded Codex catalog at $seeded_skills; skipping."
    exit 0
fi

codex_home="${CODEX_HOME:-$HOME/.codex}"
link="$codex_home/skills"

# Never replace a real directory: it holds personal skills this script did not create.
if [[ -e "$link" && ! -L "$link" ]]; then
    echo "$link is not a symlink; leaving it as-is."
    exit 0
fi

mkdir -p "$codex_home"
ln -sfn "$seeded_skills" "$link"
