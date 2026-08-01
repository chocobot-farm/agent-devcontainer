#!/usr/bin/env python3

"""
Resolution of the catalog paths requested on the command line.

The catalog no longer sits at a fixed repository location, so callers name it
with the ``plugin`` alias and let the marketplace manifests say where it lives:
``.claude-plugin/marketplace.json`` and ``.agents/plugins/marketplace.json`` are
well-known locations that already list every plugin this repository publishes.
A requested path that resolves to nothing is an error: silently validating zero
files is indistinguishable from a clean run and hides catalog regressions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, NamedTuple, Optional, Tuple

from .types import ValidationIssue, ValidationLevel, ValidationResult

# Names that stand for "every plugin this repository publishes".
PLUGIN_ALIASES = ('plugin', 'plugins')


class Ecosystem(NamedTuple):
    """Where one agent ecosystem keeps its marketplace and plugin manifests."""

    name: str
    marketplace: Path  # relative to the repository root
    manifest: Path  # relative to a plugin root


ECOSYSTEMS = {
    ecosystem.name: ecosystem
    for ecosystem in (
        Ecosystem(
            'claude',
            Path('.claude-plugin') / 'marketplace.json',
            Path('.claude-plugin') / 'plugin.json',
        ),
        Ecosystem(
            'codex',
            Path('.agents') / 'plugins' / 'marketplace.json',
            Path('.codex-plugin') / 'plugin.json',
        ),
    )
}

# Well-known marketplace manifests, relative to the repository root.
MARKETPLACE_LOCATIONS = tuple(ecosystem.marketplace for ecosystem in ECOSYSTEMS.values())


def find_plugin_roots(search_root: Path | str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Return the plugins published under ``search_root`` and any discovery errors.

    Errors are ``(source_path, message)`` pairs, reported for a marketplace that
    cannot be read and for an entry whose local source is not on disk. Remote
    sources are skipped: there is nothing local to validate.
    """
    root = Path(search_root)
    plugin_roots: List[str] = []
    errors: List[Tuple[str, str]] = []
    marketplaces = [
        root / location for location in MARKETPLACE_LOCATIONS if (root / location).is_file()
    ]

    if not marketplaces:
        locations = ', '.join(str(location) for location in MARKETPLACE_LOCATIONS)
        return [], [(str(root), f'No marketplace manifest found under {root} ({locations})')]

    for marketplace in marketplaces:
        entries, error = read_marketplace_entries(marketplace)
        if error is not None:
            errors.append((str(marketplace), error))
            continue

        for entry in entries:
            name = entry.get('name', '<unnamed>')
            source = local_source(entry.get('source'))
            if source is None:
                continue

            plugin_root = root / source
            if not plugin_root.is_dir():
                errors.append(
                    (
                        str(marketplace),
                        f"entry '{name}' points at missing plugin source {source}",
                    )
                )
                continue

            resolved = str(plugin_root)
            if resolved not in plugin_roots:
                plugin_roots.append(resolved)

    return plugin_roots, errors


def resolve_paths(
    paths: Iterable[str],
    search_root: Optional[Path | str] = None,
) -> Tuple[List[str], List[ValidationResult]]:
    """
    Expand catalog aliases and report every path that resolves to nothing.

    Literal paths are resolved as given (relative ones against the working
    directory); ``search_root`` is the repository root the marketplace manifests
    and their plugin sources are resolved against.
    """
    root = Path(search_root) if search_root is not None else Path.cwd()
    resolved: List[str] = []
    failures: List[ValidationResult] = []

    for path in paths:
        if Path(path).exists():
            resolved.append(path)
            continue

        if path not in PLUGIN_ALIASES:
            failures.append(_failure(path, 'Path does not exist'))
            continue

        plugin_roots, errors = find_plugin_roots(root)
        failures.extend(_failure(source, message) for source, message in errors)
        if plugin_roots:
            resolved.extend(plugin_roots)
        elif not errors:
            failures.append(
                _failure(path, f'No plugin is published by a marketplace under {root}')
            )

    return resolved, failures


def read_marketplace_entries(marketplace: Path) -> Tuple[List[dict], Optional[str]]:
    """Return the plugin entries of a marketplace manifest, or why it has none."""
    try:
        manifest = json.loads(marketplace.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [], f'Failed to parse marketplace manifest: {exc}'

    if not isinstance(manifest, dict):
        return [], 'Marketplace manifest must contain a JSON object'

    entries = manifest.get('plugins')
    if not isinstance(entries, list):
        return [], "Marketplace manifest has no 'plugins' list"

    return [entry for entry in entries if isinstance(entry, dict)], None


def local_source(source: object) -> Optional[str]:
    """Return the repository-relative path of a local source, else ``None``."""
    # Object form: {"source": "local", "path": "./..."}; other kinds are remote.
    if isinstance(source, dict):
        if source.get('source') != 'local':
            return None
        path = source.get('path')
        return path if isinstance(path, str) and path else None

    # String form: a path for a local plugin, an owner/repo or URL otherwise.
    if isinstance(source, str) and source.startswith(('.', '/')):
        return source

    return None


def _failure(path: str, message: str) -> ValidationResult:
    """Build the result reported for a path that cannot be validated."""
    return ValidationResult(
        skill_path=path,
        issues=[
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message=message,
                section='paths',
            )
        ],
    )


__all__ = [
    'ECOSYSTEMS',
    'Ecosystem',
    'find_plugin_roots',
    'local_source',
    'read_marketplace_entries',
    'resolve_paths',
    'MARKETPLACE_LOCATIONS',
    'PLUGIN_ALIASES',
]
