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
         "

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
