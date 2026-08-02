#!/usr/bin/env python3

"""Tests for plugin-layout validation (spec 02: manifests and catalog paths)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from validate_agent_files.main import main


def _write_plugin(
    tmp_path: Path,
    *,
    plugin_version: str,
    marketplace_version: str,
    codex_version: Optional[str] = None,
) -> Path:
    """
    Write a plugin packaged for both Claude and Codex.

    ``codex_version`` defaults to ``plugin_version``; pass ``''`` to omit the
    Codex manifest entirely.
    """
    plugin_root = tmp_path / 'plugin'
    (plugin_root / '.claude-plugin').mkdir(parents=True)
    (plugin_root / '.claude-plugin' / 'plugin.json').write_text(
        json.dumps({'name': 'agentdev', 'version': plugin_version}) + '\n'
    )
    codex_version = plugin_version if codex_version is None else codex_version
    if codex_version:
        (plugin_root / '.codex-plugin').mkdir(parents=True)
        (plugin_root / '.codex-plugin' / 'plugin.json').write_text(
            json.dumps({'name': 'agentdev', 'version': codex_version}) + '\n'
        )
    (tmp_path / '.claude-plugin').mkdir(parents=True)
    (tmp_path / '.claude-plugin' / 'marketplace.json').write_text(
        json.dumps(
            {
                'name': 'chocobot-farm',
                'plugins': [
                    {
                        'name': 'agentdev',
                        'source': './plugin',
                        'description': 'Catalog.',
                        'version': marketplace_version,
                    }
                ],
            }
        )
        + '\n'
    )
    return plugin_root


def _write_skill(plugin_root: Path, name: str, body: str) -> None:
    skill_dir = plugin_root / 'skills' / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        f"""---
name: {name}
description: A comprehensive description of what this skill does and when to use it.
---
# Overview

{body}

## When to use this skill

Use it when testing plugin layout validation.
"""
    )


def test_agreeing_manifest_versions_pass(tmp_path: Path, capsys) -> None:
    """A plugin whose manifests agree on the version validates cleanly."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.0.0')
    _write_skill(plugin_root, 'demo', 'Runs a demo.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out
    assert 'does not match' not in captured.out


def test_disagreeing_manifest_versions_fail(tmp_path: Path, capsys) -> None:
    """A marketplace entry that drifts from plugin.json is an error."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.1.0')
    _write_skill(plugin_root, 'demo', 'Runs a demo.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "'agentdev' version 1.0.0" in captured.out
    assert '1.1.0' in captured.out


def test_disagreeing_codex_manifest_version_fails(tmp_path: Path, capsys) -> None:
    """Claude and Codex package manifests must describe the same release."""
    plugin_root = _write_plugin(
        tmp_path,
        plugin_version='1.0.0',
        marketplace_version='1.0.0',
        codex_version='1.1.0',
    )
    _write_skill(plugin_root, 'demo', 'Runs a demo.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.codex-plugin/plugin.json' in captured.out
    assert "version '1.1.0'" in captured.out
    assert "version '1.0.0'" in captured.out


def test_missing_codex_manifest_is_allowed_by_default(tmp_path: Path, capsys) -> None:
    """
    Not every plugin ships for Codex, so its manifest is optional by default.

    A repository that does require it opts in with ``--require-marketplace codex``;
    see ``test_require_marketplace.py``.
    """
    plugin_root = _write_plugin(
        tmp_path,
        plugin_version='1.0.0',
        marketplace_version='1.0.0',
        codex_version='',
    )
    _write_skill(plugin_root, 'demo', 'Runs a demo.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out


def test_unparsable_plugin_manifest_fails(tmp_path: Path, capsys) -> None:
    """A plugin.json that does not parse is an error, not a crash."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.0.0')
    (plugin_root / '.claude-plugin' / 'plugin.json').write_text('{not json')
    _write_skill(plugin_root, 'demo', 'Runs a demo.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'plugin.json' in captured.out


def test_literal_catalog_path_in_skill_body_fails(tmp_path: Path, capsys) -> None:
    """A reintroduced literal `.claude/skills/` path fails validation (F6 guard)."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.0.0')
    _write_skill(plugin_root, 'demo', 'Run `.claude/skills/demo/scripts/demo.sh` to start.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.claude/skills/' in captured.out
    assert 'CLAUDE_SKILL_DIR' in captured.out


def test_skill_dir_substitution_is_accepted(tmp_path: Path, capsys) -> None:
    """The `${CLAUDE_SKILL_DIR}` replacement is not flagged."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.0.0')
    _write_skill(plugin_root, 'demo', 'Run `${CLAUDE_SKILL_DIR}/scripts/demo.sh` to start.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out


def test_personal_catalog_path_is_not_flagged(tmp_path: Path, capsys) -> None:
    """`~/.claude/agents/` still resolves for a plugin user, so it is allowed."""
    plugin_root = _write_plugin(tmp_path, plugin_version='1.0.0', marketplace_version='1.0.0')
    _write_skill(plugin_root, 'demo', 'Personal agents live in `~/.claude/agents/`.')

    exit_code = main([str(plugin_root), '--kind', 'skills'])
    captured = capsys.readouterr()

    assert exit_code == 0, captured.out
