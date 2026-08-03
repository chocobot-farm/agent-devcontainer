#!/usr/bin/env python3

"""Tests for ``--mode plugin``: packaging validated everywhere, required nowhere."""

from __future__ import annotations

import json
from pathlib import Path

from validate_agent_files.main import main

CLAUDE_MARKETPLACE = Path('.claude-plugin') / 'marketplace.json'
CODEX_MARKETPLACE = Path('.agents') / 'plugins' / 'marketplace.json'
PLUGIN_SOURCE = './.agents/plugins/agentdev'


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + '\n')


def _write_skill(plugin_root: Path, name: str = 'demo') -> None:
    skill_dir = plugin_root / 'skills' / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        f"""---
name: {name}
description: A comprehensive description of what this skill does and when to use it.
---
# Overview

Runs a demo.

## When to use this skill

Use it when testing the plugin mode.
"""
    )


def _write_repo(
    root: Path,
    *,
    plugin_version: str = '1.0.0',
    marketplace_version: str = '1.0.0',
    codex_version: str = '1.0.0',
    codex_marketplace: bool = True,
) -> Path:
    """Build a repository root that sits above the plugin it publishes."""
    plugin_root = root / PLUGIN_SOURCE
    plugin_root.mkdir(parents=True, exist_ok=True)
    _write_skill(plugin_root)
    _write_json(
        plugin_root / '.claude-plugin' / 'plugin.json',
        {'name': 'agentdev', 'version': plugin_version},
    )
    if codex_version:
        _write_json(
            plugin_root / '.codex-plugin' / 'plugin.json',
            {'name': 'agentdev', 'version': codex_version},
        )
    _write_json(
        root / CLAUDE_MARKETPLACE,
        {
            'name': 'plume-works',
            'plugins': [
                {'name': 'agentdev', 'source': PLUGIN_SOURCE, 'version': marketplace_version}
            ],
        },
    )
    if codex_marketplace:
        _write_json(
            root / CODEX_MARKETPLACE,
            {
                'name': 'plume-works',
                'plugins': [
                    {'name': 'agentdev', 'source': {'source': 'local', 'path': PLUGIN_SOURCE}}
                ],
            },
        )
    return plugin_root


def test_plugin_mode_accepts_a_consistent_repository(tmp_path, monkeypatch, capsys) -> None:
    """A repository whose packaging agrees validates cleanly in plugin mode."""
    _write_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--mode', 'plugin'])

    assert exit_code == 0, capsys.readouterr().out


def test_plugin_mode_finds_plugins_below_the_requested_path(tmp_path, monkeypatch, capsys) -> None:
    """The repository root is above its plugins, so discovery must look down."""
    _write_repo(tmp_path, plugin_version='1.0.0', marketplace_version='1.1.0')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--mode', 'plugin'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'version 1.1.0 does not match' in captured.out


def test_files_mode_leaves_packaging_alone(tmp_path, monkeypatch, capsys) -> None:
    """Without the mode, a repository root validates files and nothing else."""
    _write_repo(tmp_path, plugin_version='1.0.0', marketplace_version='1.1.0')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out
    assert 'does not match' not in captured.out


def test_plugin_mode_tolerates_a_missing_marketplace(tmp_path, monkeypatch, capsys) -> None:
    """A missing ecosystem manifest is a packaging choice, not an error."""
    _write_repo(tmp_path, codex_marketplace=False, codex_version='')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--mode', 'plugin'])

    assert exit_code == 0, capsys.readouterr().out


def test_plugin_mode_tolerates_a_missing_plugin_definition(tmp_path, monkeypatch, capsys) -> None:
    """A plugin published to Codex without a Codex manifest is not an error here."""
    _write_repo(tmp_path, codex_version='')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--mode', 'plugin'])

    assert exit_code == 0, capsys.readouterr().out


def test_required_ecosystem_still_fails_in_plugin_mode(tmp_path, monkeypatch, capsys) -> None:
    """--require-marketplace keeps its teeth: the same repository fails the gate."""
    _write_repo(tmp_path, codex_version='')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--mode', 'plugin', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.codex-plugin/plugin.json' in captured.out


def test_plugin_manifest_checked_once_when_requested_and_published(
    tmp_path, monkeypatch, capsys
) -> None:
    """A plugin reached both from the command line and from a marketplace is checked once."""
    plugin_root = _write_repo(tmp_path, plugin_version='1.0.0', marketplace_version='1.1.0')
    monkeypatch.chdir(tmp_path)

    exit_code = main([str(plugin_root), '--mode', 'plugin'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.count('version 1.1.0 does not match') == 1
