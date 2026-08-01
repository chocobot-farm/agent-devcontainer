#!/usr/bin/env python3

"""Tests for command-line path resolution (plugin alias and unusable paths)."""

from __future__ import annotations

import json
from pathlib import Path

from validate_agent_files.main import main
from validate_agent_files.paths import find_plugin_roots, resolve_paths


def _write_plugin(root: Path, relative_path: str) -> Path:
    """Create a minimal plugin catalog with one broken cross-reference."""
    plugin_root = root / relative_path
    (plugin_root / '.claude-plugin').mkdir(parents=True)
    (plugin_root / '.claude-plugin' / 'plugin.json').write_text(
        json.dumps({'name': 'agentdev', 'version': '1.0.0'}) + '\n'
    )
    (plugin_root / '.codex-plugin').mkdir(parents=True)
    (plugin_root / '.codex-plugin' / 'plugin.json').write_text(
        json.dumps({'name': 'agentdev', 'version': '1.0.0'}) + '\n'
    )
    skill_dir = plugin_root / 'skills' / 'broken-link'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        """---
name: broken-link
description: A comprehensive description of what this skill does and when to use it.
---
# Overview

See [conventions](../../../AGENTS.md) for the rules.

## When to use this skill

Use it when testing path resolution.
"""
    )
    return plugin_root


def _write_claude_marketplace(root: Path, source: object, name: str = 'agentdev') -> Path:
    """Write the Claude marketplace manifest, whose sources are plain strings."""
    marketplace = root / '.claude-plugin' / 'marketplace.json'
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                'name': 'chocobot-farm',
                'plugins': [{'name': name, 'source': source, 'version': '1.0.0'}],
            }
        )
        + '\n'
    )
    return marketplace


def _write_agents_marketplace(root: Path, path: str, name: str = 'agentdev') -> Path:
    """Write the .agents marketplace manifest, whose sources are objects."""
    marketplace = root / '.agents' / 'plugins' / 'marketplace.json'
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                'name': 'chocobot-farm',
                'plugins': [{'name': name, 'source': {'source': 'local', 'path': path}}],
            }
        )
        + '\n'
    )
    return marketplace


def test_plugin_alias_resolves_through_the_claude_marketplace(tmp_path: Path) -> None:
    """``plugin`` expands to the sources listed by .claude-plugin/marketplace.json."""
    plugin_root = _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert failures == []
    assert [Path(path) for path in resolved] == [plugin_root]


def test_plugin_alias_resolves_an_object_source(tmp_path: Path) -> None:
    """A ``{"source": "local", "path": ...}`` entry resolves like a string source."""
    plugin_root = _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_agents_marketplace(tmp_path, './.agents/plugins/agentdev')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert failures == []
    assert [Path(path) for path in resolved] == [plugin_root]


def test_plugin_alias_lists_each_plugin_once(tmp_path: Path) -> None:
    """A plugin published by both marketplaces is validated once."""
    plugin_root = _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')
    _write_agents_marketplace(tmp_path, './.agents/plugins/agentdev')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert failures == []
    assert [Path(path) for path in resolved] == [plugin_root]


def test_plugin_alias_ignores_remote_sources(tmp_path: Path) -> None:
    """A remote source has nothing local to validate, and is not an error."""
    plugin_root = _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_agents_marketplace(tmp_path, './.agents/plugins/agentdev')
    marketplace = json.loads((tmp_path / '.agents/plugins/marketplace.json').read_text())
    marketplace['plugins'].append({'name': 'remote', 'source': 'chocobot-farm/other-plugin'})
    (tmp_path / '.agents/plugins/marketplace.json').write_text(json.dumps(marketplace))

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert failures == []
    assert [Path(path) for path in resolved] == [plugin_root]


def test_plugin_alias_prefers_an_existing_directory_of_that_name(
    tmp_path: Path, monkeypatch
) -> None:
    """A real ``plugin`` directory wins over the alias."""
    (tmp_path / 'plugin').mkdir()
    _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')
    monkeypatch.chdir(tmp_path)

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert failures == []
    assert [Path(path) for path in resolved] == [Path('plugin')]


def test_missing_marketplace_is_an_error(tmp_path: Path) -> None:
    """The alias fails loudly when neither well-known manifest exists."""
    _write_plugin(tmp_path, '.agents/plugins/agentdev')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert resolved == []
    assert 'No marketplace manifest found' in failures[0].issues[0].message


def test_marketplace_entry_pointing_at_a_missing_source_is_an_error(tmp_path: Path) -> None:
    """A published source that has moved away is reported, not skipped."""
    _write_claude_marketplace(tmp_path, './plugins/agentdev')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert resolved == []
    assert 'missing plugin source ./plugins/agentdev' in failures[0].issues[0].message


def test_unparsable_marketplace_is_an_error(tmp_path: Path) -> None:
    """A manifest that cannot be read fails instead of resolving to nothing."""
    marketplace = tmp_path / '.claude-plugin' / 'marketplace.json'
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text('{ not json')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert resolved == []
    assert 'Failed to parse marketplace manifest' in failures[0].issues[0].message


def test_marketplace_without_local_plugins_is_an_error(tmp_path: Path) -> None:
    """A marketplace publishing only remote plugins leaves nothing to validate."""
    _write_claude_marketplace(tmp_path, 'chocobot-farm/other-plugin')

    resolved, failures = resolve_paths(['plugin'], search_root=tmp_path)

    assert resolved == []
    assert 'No plugin is published by a marketplace' in failures[0].issues[0].message


def test_unknown_path_is_an_error(tmp_path: Path) -> None:
    """A path that does not exist fails instead of validating nothing."""
    resolved, failures = resolve_paths([str(tmp_path / 'missing')], search_root=tmp_path)

    assert resolved == []
    assert len(failures) == 1
    assert 'does not exist' in failures[0].issues[0].message


def test_cli_path_without_catalog_files_fails(tmp_path: Path, capsys) -> None:
    """A path that exists but holds no catalog validates nothing, so it fails."""
    empty = tmp_path / 'docs'
    empty.mkdir()
    (empty / 'README.md').write_text('Not a catalog file.\n')

    exit_code = main([str(empty)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'no skills, agents, or prompts' in captured.out


def test_cli_kind_filter_does_not_fail_a_real_catalog(tmp_path: Path, monkeypatch, capsys) -> None:
    """A skills-only catalog asked for agents is empty by request, not broken."""
    _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['plugin', '--kind', 'agents'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out
    assert 'no skills, agents, or prompts' not in captured.out


def test_find_plugin_roots_reports_sources_and_errors(tmp_path: Path) -> None:
    """Discovery returns resolved plugin roots alongside per-source errors."""
    plugin_root = _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')
    _write_agents_marketplace(tmp_path, './.agents/plugins/moved-away', name='moved')

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert [Path(path) for path in plugin_roots] == [plugin_root]
    assert len(errors) == 1
    assert errors[0][0].endswith('.agents/plugins/marketplace.json')


def test_cli_plugin_alias_reports_broken_references(tmp_path: Path, monkeypatch, capsys) -> None:
    """``validate_agent_files plugin`` validates the published catalog."""
    _write_plugin(tmp_path, '.agents/plugins/agentdev')
    _write_claude_marketplace(tmp_path, './.agents/plugins/agentdev')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['plugin', '--kind', 'skills'])

    assert exit_code == 1
    assert 'Broken reference: ../../../AGENTS.md' in capsys.readouterr().out


def test_cli_missing_path_fails(tmp_path: Path, capsys) -> None:
    """A missing path makes the CLI fail rather than silently pass."""
    exit_code = main([str(tmp_path / 'missing')])

    assert exit_code == 1
    assert 'does not exist' in capsys.readouterr().out
