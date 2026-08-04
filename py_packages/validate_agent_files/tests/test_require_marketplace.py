#!/usr/bin/env python3

"""Tests for ``--require-marketplace``: opt-in per-ecosystem packaging gates."""

from __future__ import annotations

from pathlib import Path

from mock_catalog import (
    claude_entry,
    CLAUDE_MANIFEST,
    codex_entry,
    CODEX_MANIFEST,
    CODEX_MARKETPLACE,
    plugin_manifest,
    PLUGIN_NAME,
    PLUGIN_SOURCE,
    write_claude_marketplace,
    write_codex_marketplace,
    write_json,
    write_skill,
)
from validate_agent_files.main import main


def _write_repo(
    root: Path,
    *,
    claude_marketplace: bool = True,
    codex_marketplace: bool = True,
    claude_manifest: object = 'default',
    codex_manifest: object = 'default',
    source: str = PLUGIN_SOURCE,
) -> Path:
    """Build a repository publishing one plugin to both ecosystems."""
    plugin_root = root / PLUGIN_SOURCE
    plugin_root.mkdir(parents=True, exist_ok=True)
    write_skill(plugin_root, usage='Use it when testing marketplace requirements.')

    if claude_manifest is not None:
        payload = plugin_manifest() if claude_manifest == 'default' else claude_manifest
        write_json(plugin_root / CLAUDE_MANIFEST, payload)
    if codex_manifest is not None:
        payload = plugin_manifest() if codex_manifest == 'default' else codex_manifest
        write_json(plugin_root / CODEX_MANIFEST, payload)

    if claude_marketplace:
        write_claude_marketplace(root, claude_entry(source=source))
    if codex_marketplace:
        write_codex_marketplace(root, codex_entry(path=source))
    return plugin_root


def test_complete_repository_satisfies_both_ecosystems(tmp_path, monkeypatch, capsys) -> None:
    """A plugin published to both marketplaces passes both requirements."""
    _write_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex', 'claude'])

    assert exit_code == 0, capsys.readouterr().out


def test_requirement_checks_the_plugin_manifest_from_the_repository_root(
    tmp_path, monkeypatch, capsys
) -> None:
    """Requiring an ecosystem also cross-checks plugin.json against its entry."""
    _write_repo(tmp_path)
    write_claude_marketplace(tmp_path, claude_entry(version='1.1.0'))
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'claude'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'version 1.1.0 does not match' in captured.out


def test_requirement_is_opt_in(tmp_path, monkeypatch, capsys) -> None:
    """Without the flag a Claude-only plugin is valid: the tool stays generic."""
    _write_repo(tmp_path, codex_marketplace=False, codex_manifest=None)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.'])

    assert exit_code == 0, capsys.readouterr().out


def test_missing_codex_marketplace_fails(tmp_path, monkeypatch, capsys) -> None:
    """A required marketplace file that is absent is an error."""
    _write_repo(tmp_path, codex_marketplace=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.agents/plugins/marketplace.json' in captured.out
    assert 'required' in captured.out


def test_missing_claude_marketplace_fails(tmp_path, monkeypatch, capsys) -> None:
    """The requirement applies to the Claude ecosystem too, not just Codex."""
    _write_repo(tmp_path, claude_marketplace=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'claude'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.claude-plugin/marketplace.json' in captured.out


def test_marketplace_entry_pointing_at_missing_plugin_fails(tmp_path, monkeypatch, capsys) -> None:
    """A referenced plugin that is not on disk is an error."""
    _write_repo(tmp_path)
    write_codex_marketplace(tmp_path, codex_entry(path='./.agents/plugins/gone', name='gone'))
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'gone' in captured.out


def test_missing_ecosystem_manifest_fails(tmp_path, monkeypatch, capsys) -> None:
    """A published plugin lacking that ecosystem's plugin.json is an error."""
    _write_repo(tmp_path, codex_manifest=None)
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.codex-plugin/plugin.json' in captured.out
    assert 'missing' in captured.out


def test_unparsable_ecosystem_manifest_fails(tmp_path, monkeypatch, capsys) -> None:
    """A plugin.json that does not parse is an error, not a crash."""
    _write_repo(tmp_path)
    (tmp_path / PLUGIN_SOURCE / CODEX_MANIFEST).write_text('{not json')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.codex-plugin/plugin.json' in captured.out


def test_ecosystem_manifest_without_required_fields_fails(tmp_path, monkeypatch, capsys) -> None:
    """A plugin definition must declare a name and a version."""
    _write_repo(tmp_path, codex_manifest={'description': 'No name, no version.'})
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'name' in captured.out
    assert 'version' in captured.out


def test_ecosystem_manifest_name_must_match_the_entry(tmp_path, monkeypatch, capsys) -> None:
    """A definition naming a different plugin than the marketplace is an error."""
    _write_repo(tmp_path, codex_manifest=plugin_manifest(name='other'))
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "'other'" in captured.out
    assert f"'{PLUGIN_NAME}'" in captured.out


def test_unparsable_required_marketplace_fails(tmp_path, monkeypatch, capsys) -> None:
    """A required marketplace that does not parse is an error."""
    _write_repo(tmp_path)
    (tmp_path / CODEX_MARKETPLACE).write_text('{not json')
    monkeypatch.chdir(tmp_path)

    exit_code = main(['.', '--require-marketplace', 'codex'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert '.agents/plugins/marketplace.json' in captured.out
