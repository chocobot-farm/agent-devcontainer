# Tag-only by design. CI always overrides this with an explicit digest built in the same
# run (see .github/workflows/ci.yml); pinning a digest here would make Renovate bump a file
# under docker/**, which matches the CI image path filter and rebuilds the very image that
# produced the digest — an endless bump/rebuild loop.
ARG FROM_IMAGE=ghcr.io/plume-works/ubuntu-ansible:edge

FROM $FROM_IMAGE

# Default workspace folder. Consumers override it at runtime with
# DEV_WORKSPACE_FOLDER (set by .devcontainer/devcontainer.json), so this only
# provides the fallback baked into the image.
ARG WORKSPACE_FOLDER=/workspaces/project

# Version of the agentdev catalog seeded into the image. The catalog is seeded from
# the build context, so this is a pin the build verifies rather than a version it
# fetches: .claude-plugin/marketplace.json must declare exactly this version or the
# provisioning fails. Bump both together when releasing the catalog.
ARG AGENTDEV_PLUGIN_VERSION=3.0.0

# Where the seeded catalog lives. Outside $HOME on purpose: ~/.claude and ~/.codex
# are commonly mounted as volumes, which would shadow anything placed under them.
ARG AGENTDEV_SEED_DIR=/opt/agentdev-seed

# Provision the image with Ansible.
#
# The build context is the repository root, bind-mounted read-only rather than
# COPY'd so none of the provisioning sources end up in the final layer. Omitting
# `source` on the bind mount takes the whole context.
# `cd` (not WORKDIR) into /provision/ansible: that path only exists for the
# duration of this RUN's bind mount, so WORKDIR would break later build steps.
# hadolint ignore=DL3003
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=bind,readonly,target=/provision \
    apt-get update \
    && cd /provision/ansible \
    && ansible-playbook playbooks/setup-dev.yml \
      -vvv \
      -e "workspace_folder=$WORKSPACE_FOLDER \
           install_xpra=true \
           install_docker=true \
           install_agentic_tools=true \
           install_devcontainer_firewall=true \
           agentic_tools_seed_plugins=true \
           agentic_tools_seed_source_dir=/provision \
           agentic_tools_plugin_version=$AGENTDEV_PLUGIN_VERSION \
           agentic_tools_seed_root=$AGENTDEV_SEED_DIR \
         "

# Inherited by any consumer of this image, including one that writes its own
# devcontainer.json and knows nothing about the seed. Claude Code registers the
# seeded marketplaces at session start and uses the seeded cache in place; a
# project that is itself the catalog's source opts out by setting this to "".
ENV AGENTDEV_SEED_DIR=$AGENTDEV_SEED_DIR
ENV CLAUDE_CODE_PLUGIN_SEED_DIR=$AGENTDEV_SEED_DIR/claude

LABEL org.opencontainers.image.version.agentdev="$AGENTDEV_PLUGIN_VERSION"

WORKDIR $WORKSPACE_FOLDER

# Xpra HTML5 client startup script
COPY --chmod=755 docker/desktop/start-xpra.sh /start-xpra.sh

# Xpra HTML5 base port. start-xpra.sh derives a per-devcontainer port in
# 14500-14599 from DEVCONTAINER_ID so parallel worktrees do not collide.
EXPOSE 14500

ENV PATH="/root/.local/bin:$PATH"

COPY --chmod=755 docker/desktop/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
