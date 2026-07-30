#!/usr/bin/env bash
# Container entrypoint. Nothing to source — the image ships a plain development
# environment — so just hand off to the requested command.
set -e

exec "$@"
