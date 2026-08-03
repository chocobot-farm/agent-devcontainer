#!/usr/bin/env python3

"""Tests for command-line path resolution and marketplace-driven plugin discovery."""

from __future__ import annotations

import json
from pathlib import Path

from mock_catalog import (
    CLAUDE_MANIFEST,
    codex_entry,
    CODEX_MANIFEST,
    CODEX_MARKETPLACE,
    PLUGIN_DIR,
    plugin_manifest,
    REMOTE_SOURCE,
    write_claude_marketplace,
    write_codex_marketplace,
    write_json,
)
from validate_agent_files.main import main
from validate_agent_files.paths import find_plugin_roots, resolve_paths


def _write_plugin(root: Path, relative_path: str = PLUGIN_DIR) -> Path:
    """Create a minimal plugin catalog with one broken cross-reference."""
    plugin_root = root / relative_path
    write_json(plugin_root / CLAUDE_MANIFEST, plugin_manifest())
    write_json(plugin_root / CODEX_MANIFEST, plugin_manifest())
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


def test_existing_paths_are_kept_as_given(tmp_path: Path) -> None:
    """A path that exists is validated as written, without rewriting."""
    plugin_root = _write_plugin(tmp_path)

    resolved, failures = resolve_paths([str(plugin_root)])

    assert failures == []
    assert [Path(path) for path in resolved] == [plugin_root]


def test_unknown_path_is_an_error(tmp_path: Path) -> None:
    """A path that does not exist fails instead of validating nothing."""
    resolved, failures = resolve_paths([str(tmp_path / 'missing')])

    assert resolved == []
    assert len(failures) == 1
    assert 'does not exist' in failures[0].issues[0].message


def test_plugin_is_not_a_path_alias(tmp_path: Path, monkeypatch) -> None:
    """``plugin`` is a path like any other: absent means an error, not a catalog."""
    _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    monkeypatch.chdir(tmp_path)

    resolved, failures = resolve_paths(['plugin'])

    assert resolved == []
    assert 'does not exist' in failures[0].issues[0].message


def test_cli_rejects_the_former_plugin_alias(tmp_path: Path, monkeypatch, capsys) -> None:
    """The retired alias fails loudly rather than silently validating the catalog."""
    _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['plugin', '--require-marketplace', 'claude'])

    assert exit_code == 1
    assert 'does not exist' in capsys.readouterr().out


def test_find_plugin_roots_resolves_a_string_source(tmp_path: Path) -> None:
    """Discovery expands the sources listed by .claude-plugin/marketplace.json."""
    plugin_root = _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert errors == []
    assert [Path(path) for path in plugin_roots] == [plugin_root]


def test_find_plugin_roots_resolves_an_object_source(tmp_path: Path) -> None:
    """A ``{"source": "local", "path": ...}`` entry resolves like a string source."""
    plugin_root = _write_plugin(tmp_path)
    write_codex_marketplace(tmp_path)

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert errors == []
    assert [Path(path) for path in plugin_roots] == [plugin_root]


def test_find_plugin_roots_lists_each_plugin_once(tmp_path: Path) -> None:
    """A plugin published by both marketplaces is discovered once."""
    plugin_root = _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    write_codex_marketplace(tmp_path)

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert errors == []
    assert [Path(path) for path in plugin_roots] == [plugin_root]


def test_find_plugin_roots_ignores_remote_sources(tmp_path: Path) -> None:
    """A remote source has nothing local to validate, and is not an error."""
    plugin_root = _write_plugin(tmp_path)
    write_codex_marketplace(tmp_path)
    marketplace = json.loads((tmp_path / CODEX_MARKETPLACE).read_text())
    marketplace['plugins'].append({'name': 'remote', 'source': REMOTE_SOURCE})
    (tmp_path / CODEX_MARKETPLACE).write_text(json.dumps(marketplace))

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert errors == []
    assert [Path(path) for path in plugin_roots] == [plugin_root]


def test_find_plugin_roots_reports_sources_and_errors(tmp_path: Path) -> None:
    """Discovery returns resolved plugin roots alongside per-source errors."""
    plugin_root = _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    write_codex_marketplace(
        tmp_path, codex_entry(path='./.agents/plugins/moved-away', name='moved')
    )

    plugin_roots, errors = find_plugin_roots(tmp_path)

    assert [Path(path) for path in plugin_roots] == [plugin_root]
    assert len(errors) == 1
    assert errors[0][0].endswith(str(CODEX_MARKETPLACE))


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
    _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--kind', 'agents'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out
    assert 'no skills, agents, or prompts' not in captured.out


def test_cli_reports_broken_references_under_a_repository_root(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Validating the repository root reaches the skills of its plugins."""
    _write_plugin(tmp_path)
    write_claude_marketplace(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--kind', 'skills'])

    # The fixture's reference both escapes the plugin and dangles; containment
    # is the finding reported, because it is wrong wherever the plugin lands.
    assert exit_code == 1
    assert 'Reference ../../../AGENTS.md resolves outside the plugin root' in (
        capsys.readouterr().out
    )


def test_cli_missing_path_fails(tmp_path: Path, capsys) -> None:
    """A missing path makes the CLI fail rather than silently pass."""
    exit_code = main([str(tmp_path / 'missing')])

    assert exit_code == 1
    assert 'does not exist' in capsys.readouterr().out
