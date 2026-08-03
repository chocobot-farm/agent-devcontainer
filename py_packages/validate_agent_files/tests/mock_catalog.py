#!/usr/bin/env python3

"""
Mock catalog data for the tests: a fictional repository, never this one.

``validate_agent_files`` is a general tool, so its tests describe a repository
that does not exist rather than the one they happen to ship in. Every identity
below — the marketplace name, the plugin name, and the directory the plugin is
published from — is made up on purpose, so renaming this repository's own
marketplace or plugin can never require a test edit.

Manifest *locations* are the exception. ``.claude-plugin/marketplace.json`` and
the rest are part of the tool's contract with the Claude and Codex ecosystems,
not any one repository's identity, so they are imported from
:mod:`validate_agent_files.paths` rather than restated here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from validate_agent_files.paths import ECOSYSTEMS

# --- Identity of the fictional repository under test -------------------------

MARKETPLACE_NAME = 'mock-marketplace'
PLUGIN_NAME = 'mockplugin'
PLUGIN_VERSION = '1.0.0'

# Plugins are published as siblings of the Codex marketplace manifest, which is
# the ecosystem's layout; only the leaf directory is this fixture's own name.
PLUGIN_DIR = f'.agents/plugins/{PLUGIN_NAME}'
PLUGIN_SOURCE = f'./{PLUGIN_DIR}'

# A source that is not a local path, so discovery has something to skip.
REMOTE_SOURCE = 'mock-owner/mock-remote-plugin'

# --- Manifest locations, taken from the tool rather than restated -------------

CLAUDE_MARKETPLACE = ECOSYSTEMS['claude'].marketplace
CODEX_MARKETPLACE = ECOSYSTEMS['codex'].marketplace
CLAUDE_MANIFEST = ECOSYSTEMS['claude'].manifest
CODEX_MANIFEST = ECOSYSTEMS['codex'].manifest


def write_json(path: Path, payload: object) -> Path:
    """Write ``payload`` as JSON, creating any missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + '\n')
    return path


def plugin_manifest(
    version: str = PLUGIN_VERSION,
    name: str = PLUGIN_NAME,
) -> Dict[str, Any]:
    """Build the minimal plugin definition a marketplace entry must agree with."""
    return {'name': name, 'version': version}


def claude_entry(
    source: str = PLUGIN_SOURCE,
    version: str = PLUGIN_VERSION,
    name: str = PLUGIN_NAME,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a Claude marketplace entry, whose source is a plain path string."""
    return {'name': name, 'source': source, 'version': version, **extra}


def codex_entry(
    path: str = PLUGIN_SOURCE,
    name: str = PLUGIN_NAME,
) -> Dict[str, Any]:
    """Build a Codex marketplace entry, whose source is a local-source object."""
    return {'name': name, 'source': {'source': 'local', 'path': path}}


def write_claude_marketplace(root: Path, *entries: Dict[str, Any]) -> Path:
    """Publish ``entries`` from the Claude marketplace manifest of ``root``."""
    return _write_marketplace(root / CLAUDE_MARKETPLACE, entries or (claude_entry(),))


def write_codex_marketplace(root: Path, *entries: Dict[str, Any]) -> Path:
    """Publish ``entries`` from the Codex marketplace manifest of ``root``."""
    return _write_marketplace(root / CODEX_MARKETPLACE, entries or (codex_entry(),))


def write_skill(
    plugin_root: Path,
    name: str = 'demo',
    body: str = 'Runs a demo.',
    usage: str = 'Use it when testing the validator.',
) -> Path:
    """Write one valid skill into a plugin, so the catalog is not empty."""
    skill = plugin_root / 'skills' / name / 'SKILL.md'
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"""---
name: {name}
description: A comprehensive description of what this skill does and when to use it.
---
# Overview

{body}

## When to use this skill

{usage}
"""
    )
    return skill


def _write_marketplace(path: Path, entries: Iterable[Dict[str, Any]]) -> Path:
    """Write a marketplace manifest publishing ``entries``."""
    return write_json(path, {'name': MARKETPLACE_NAME, 'plugins': list(entries)})


__all__ = [
    'CLAUDE_MANIFEST',
    'CLAUDE_MARKETPLACE',
    'CODEX_MANIFEST',
    'CODEX_MARKETPLACE',
    'MARKETPLACE_NAME',
    'PLUGIN_DIR',
    'PLUGIN_NAME',
    'PLUGIN_SOURCE',
    'PLUGIN_VERSION',
    'REMOTE_SOURCE',
    'claude_entry',
    'codex_entry',
    'plugin_manifest',
    'write_claude_marketplace',
    'write_codex_marketplace',
    'write_json',
    'write_skill',
]
