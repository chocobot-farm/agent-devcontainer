#!/usr/bin/env python3

"""
Opt-in checks that a repository really publishes its plugins to an ecosystem.

Discovery elsewhere is deliberately forgiving: a plugin that ships for Claude but
not Codex is a normal plugin, so a missing manifest cannot be an error by default
without making the validator specific to one repository's packaging choices.

A repository that *does* promise both says so with ``--require-marketplace claude
codex``. For each named ecosystem this asserts the promise end to end: the
marketplace manifest exists and parses, every plugin it references is on disk,
and each of those plugins carries a usable definition for that ecosystem.

``validate_present_marketplaces`` runs the same walk for ``--mode plugin``, where
packaging is validated but not required: a marketplace or plugin definition that
is simply absent is skipped, while everything present is held to the same rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Sequence

from ..paths import Ecosystem, ECOSYSTEMS, local_source, read_marketplace_entries
from ..types import ValidationIssue, ValidationLevel, ValidationResult

SECTION = 'marketplace'


def validate_required_marketplaces(
    required: Sequence[str],
    search_root: Optional[Path | str] = None,
) -> List[ValidationResult]:
    """Validate that every named ecosystem publishes an installable catalog."""
    root = Path(search_root) if search_root is not None else Path.cwd()
    results: List[ValidationResult] = []

    for name in dict.fromkeys(required):
        ecosystem = ECOSYSTEMS.get(name)
        if ecosystem is None:
            known = ', '.join(sorted(ECOSYSTEMS))
            results.append(_failure(name, f'Unknown ecosystem {name!r} (known: {known})'))
            continue
        results.extend(_validate_ecosystem(ecosystem, root, required=True))

    return results


def validate_present_marketplaces(
    skip: Sequence[str] = (),
    search_root: Optional[Path | str] = None,
) -> List[ValidationResult]:
    """
    Validate the packaging every ecosystem already ships, requiring none of it.

    Ecosystems named in ``skip`` are left to ``validate_required_marketplaces``
    so a required ecosystem is not validated twice.
    """
    root = Path(search_root) if search_root is not None else Path.cwd()
    skipped = set(skip)
    results: List[ValidationResult] = []

    for name, ecosystem in ECOSYSTEMS.items():
        if name in skipped:
            continue
        results.extend(_validate_ecosystem(ecosystem, root, required=False))

    return results


def _validate_ecosystem(
    ecosystem: Ecosystem, root: Path, *, required: bool
) -> List[ValidationResult]:
    """Validate one ecosystem's marketplace and every plugin it publishes."""
    marketplace = root / ecosystem.marketplace
    if not marketplace.is_file():
        if not required:
            return []
        return [
            _failure(
                str(marketplace),
                f'{ecosystem.marketplace} is missing, but the {ecosystem.name} '
                f'marketplace is required',
            )
        ]

    entries, error = read_marketplace_entries(marketplace)
    if error is not None:
        return [_failure(str(marketplace), error)]

    if not entries:
        return [_failure(str(marketplace), f'{ecosystem.marketplace} publishes no plugins')]

    results: List[ValidationResult] = []
    for entry in entries:
        results.extend(_validate_entry(ecosystem, root, marketplace, entry, required=required))
    return results


def _validate_entry(
    ecosystem: Ecosystem,
    root: Path,
    marketplace: Path,
    entry: dict,
    *,
    required: bool,
) -> List[ValidationResult]:
    """Validate one marketplace entry and the plugin definition it points at."""
    name = entry.get('name', '<unnamed>')
    source = local_source(entry.get('source'))
    if source is None:
        # Remote plugins are published elsewhere; there is nothing local to check.
        return []

    plugin_root = root / source
    if not plugin_root.is_dir():
        return [
            _failure(str(marketplace), f"entry '{name}' points at missing plugin source {source}")
        ]

    manifest_path = plugin_root / ecosystem.manifest
    if not manifest_path.is_file():
        if not required:
            # Shipping for one ecosystem and not another is a normal choice.
            return []
        return [
            _failure(
                str(manifest_path),
                f'{ecosystem.manifest} is missing, so {ecosystem.name} cannot install '
                f"plugin '{name}'",
            )
        ]

    return _validate_definition(ecosystem, manifest_path, name)


def _validate_definition(
    ecosystem: Ecosystem,
    manifest_path: Path,
    entry_name: str,
) -> List[ValidationResult]:
    """Validate the plugin definition a marketplace entry resolves to."""
    result = ValidationResult(skill_path=str(manifest_path), issues=[])

    try:
        definition = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result.issues.append(_issue(f'Failed to parse {manifest_path}: {exc}'))
        return [result]

    if not isinstance(definition, dict):
        result.issues.append(_issue(f'{manifest_path} must contain a JSON object'))
        return [result]

    for field in ('name', 'version'):
        if not definition.get(field):
            result.issues.append(_issue(f'{manifest_path} is missing a {field}'))

    declared = definition.get('name')
    if declared and declared != entry_name:
        result.issues.append(
            _issue(
                f'{manifest_path} declares plugin {declared!r} but '
                f'{ecosystem.marketplace} publishes it as {entry_name!r}'
            )
        )

    return [result]


def _issue(message: str) -> ValidationIssue:
    """Build an error issue for the marketplace section."""
    return ValidationIssue(level=ValidationLevel.ERROR, message=message, section=SECTION)


def _failure(path: str, message: str) -> ValidationResult:
    """Build a single-issue failure result."""
    return ValidationResult(skill_path=path, issues=[_issue(message)])


__all__ = ['validate_present_marketplaces', 'validate_required_marketplaces']
