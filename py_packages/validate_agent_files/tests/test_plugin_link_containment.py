#!/usr/bin/env python3

"""Tests for plugin-root containment of markdown cross-references."""

from __future__ import annotations

from pathlib import Path
from typing import List

from validate_agent_files.types import ValidationIssue, ValidationLevel
from validate_agent_files.validators.cross_reference import CrossReferenceValidator


def _build_plugin(tmp_path: Path) -> Path:
    """Create a plugin tree with a sibling skill and a repository-root file."""
    plugin_root = tmp_path / 'plugin'
    (plugin_root / 'skills' / 'demo').mkdir(parents=True)
    (plugin_root / 'skills' / 'git-commit').mkdir(parents=True)
    (plugin_root / 'skills' / 'git-commit' / 'SKILL.md').write_text('# Git commit\n')
    (tmp_path / 'AGENTS.md').write_text('# Conventions\n')
    return plugin_root


def _validate(plugin_root: Path, content: str, plugin_aware: bool = True) -> List[ValidationIssue]:
    """Run the cross-reference validator over a skill body inside the plugin."""
    skill_dir = plugin_root / 'skills' / 'demo'
    validator = CrossReferenceValidator(
        base_path=str(skill_dir),
        plugin_root=str(plugin_root) if plugin_aware else None,
    )
    return validator.validate(
        skill_path=str(skill_dir / 'SKILL.md'),
        metadata={},
        content=content,
    )


def _escapes(issues: List[ValidationIssue]) -> List[ValidationIssue]:
    """Return only the issues reporting a reference that leaves the plugin."""
    return [issue for issue in issues if 'outside the plugin root' in issue.message]


def test_intra_plugin_link_is_accepted(tmp_path):
    """A link to a sibling skill stays inside the plugin and is not flagged."""
    plugin_root = _build_plugin(tmp_path)

    issues = _validate(plugin_root, 'See [git-commit](../git-commit/SKILL.md).')

    assert issues == []


def test_reference_escaping_the_plugin_is_an_error(tmp_path):
    """A link climbing out to the repository root is rejected with remediation."""
    plugin_root = _build_plugin(tmp_path)

    issues = _escapes(_validate(plugin_root, 'See [AGENTS.md](../../../AGENTS.md).'))

    assert len(issues) == 1
    assert issues[0].level == ValidationLevel.ERROR
    assert issues[0].section == 'cross_reference'
    assert 'prose' in issues[0].message


def test_escaping_reference_is_reported_once(tmp_path):
    """An escaping link that exists on disk is not also reported as broken."""
    plugin_root = _build_plugin(tmp_path)

    issues = _validate(plugin_root, 'See [AGENTS.md](../../../AGENTS.md).')

    assert len(issues) == 1
    assert 'Broken reference' not in issues[0].message


def test_absolute_urls_and_anchors_are_skipped(tmp_path):
    """External URLs and in-document anchors are not filesystem references."""
    plugin_root = _build_plugin(tmp_path)

    content = 'See [repo](https://example.com/repo) and [section](#usage).'

    assert _validate(plugin_root, content) == []


def test_files_outside_a_plugin_are_unaffected(tmp_path):
    """Without a plugin root the same link keeps its previous behavior."""
    plugin_root = _build_plugin(tmp_path)

    issues = _validate(
        plugin_root,
        'See [AGENTS.md](../../../AGENTS.md).',
        plugin_aware=False,
    )

    assert _escapes(issues) == []


def test_ignore_markers_suppress_the_escape_check(tmp_path):
    """The existing ignore-cross-reference markers also cover containment."""
    plugin_root = _build_plugin(tmp_path)

    content = (
        '<!-- validate_skills: ignore-cross-reference-start -->\n'
        'See [AGENTS.md](../../../AGENTS.md).\n'
        '<!-- validate_skills: ignore-cross-reference-end -->\n'
    )

    assert _validate(plugin_root, content) == []


def test_escape_is_flagged_even_when_the_target_is_missing(tmp_path):
    """A reference that both escapes and dangles reports the escape."""
    plugin_root = _build_plugin(tmp_path)

    issues = _validate(plugin_root, 'See [ruff](../../../.ruff.toml).')

    assert len(issues) == 1
    assert 'outside the plugin root' in issues[0].message
