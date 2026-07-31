#!/usr/bin/env python3

"""
Validation for the Claude Code plugin manifests that carry this catalog.

The catalog ships as the ``agentdev`` plugin: ``<plugin>/.claude-plugin/plugin.json``
declares it and ``<repo>/.claude-plugin/marketplace.json`` publishes it. Both
record a ``version`` and nothing but convention keeps the two in step, so a
mismatch is an error rather than a warning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ..types import ValidationIssue, ValidationLevel, ValidationResult

PLUGIN_MANIFEST = Path('.claude-plugin') / 'plugin.json'
MARKETPLACE_MANIFEST = Path('.claude-plugin') / 'marketplace.json'


def find_plugin_root(path: str) -> Optional[Path]:
    """Return the plugin root at or above ``path``, if there is one."""
    candidate = Path(path).resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for directory in (candidate, *candidate.parents):
        if (directory / PLUGIN_MANIFEST).is_file():
            return directory
    return None


def validate_plugin_manifests(plugin_root: Path) -> ValidationResult:
    """Validate a plugin manifest and its marketplace entry."""
    manifest_path = plugin_root / PLUGIN_MANIFEST
    result = ValidationResult(skill_path=str(manifest_path), issues=[])

    plugin_manifest = _load_json(manifest_path, result)
    if plugin_manifest is None:
        return result

    plugin_name = plugin_manifest.get('name')
    plugin_version = plugin_manifest.get('version')
    for field, value in (('name', plugin_name), ('version', plugin_version)):
        if not value:
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f'{manifest_path} is missing a {field}',
                    section='plugin-manifest',
                )
            )
    if not plugin_name or not plugin_version:
        return result

    marketplace_path = _find_marketplace(plugin_root)
    if marketplace_path is None:
        return result

    marketplace = _load_json(marketplace_path, result)
    if marketplace is None:
        return result

    entries = [
        entry
        for entry in marketplace.get('plugins', [])
        if isinstance(entry, dict) and entry.get('name') == plugin_name
    ]
    if not entries:
        result.issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message=f"{marketplace_path} has no entry for plugin '{plugin_name}'",
                section='plugin-manifest',
            )
        )
        return result

    for entry in entries:
        entry_version = entry.get('version')
        if entry_version != plugin_version:
            result.issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=(
                        f"{marketplace_path} entry '{plugin_name}' version "
                        f'{entry_version} does not match {manifest_path} '
                        f"plugin '{plugin_name}' version {plugin_version}"
                    ),
                    section='plugin-manifest',
                )
            )

    return result


def _find_marketplace(plugin_root: Path) -> Optional[Path]:
    """Return the marketplace manifest publishing ``plugin_root``, if present."""
    for directory in (plugin_root, *plugin_root.parents):
        candidate = directory / MARKETPLACE_MANIFEST
        if candidate.is_file():
            return candidate
    return None


def _load_json(path: Path, result: ValidationResult) -> Optional[dict]:
    try:
        loaded = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result.issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message=f'Failed to parse {path}: {exc}',
                section='plugin-manifest',
            )
        )
        return None

    if not isinstance(loaded, dict):
        result.issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message=f'{path} must contain a JSON object',
                section='plugin-manifest',
            )
        )
        return None

    return loaded


__all__: List[str] = ['find_plugin_root', 'validate_plugin_manifests']
