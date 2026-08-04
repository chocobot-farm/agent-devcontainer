#!/usr/bin/env python3

"""Behavior tests for the update-branch skill script."""

from __future__ import annotations

from pathlib import Path
import subprocess


def test_update_branch_reports_declared_result_when_fetch_fails(
    repo_tmp_path: Path,
) -> None:
    """A missing selected remote must produce the stable fetch-failure result."""
    # Arrange
    repository_root = Path(__file__).resolve().parents[3]
    script = (
        repository_root / '.agents/plugins/agentdev/skills/update-branch/scripts/update-branch.sh'
    )
    mock_repository = repo_tmp_path / 'fixture-repository'
    mock_repository.mkdir()
    subprocess.run(
        ['git', 'init', '--initial-branch=fixture-feature'],
        cwd=mock_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    (mock_repository / 'fixture.txt').write_text('fixture data\n')
    subprocess.run(
        ['git', 'add', 'fixture.txt'],
        cwd=mock_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            'git',
            '-c',
            'user.name=Fixture Author',
            '-c',
            'user.email=fixture@example.invalid',
            'commit',
            '-m',
            'fixture commit',
        ],
        cwd=mock_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    # Act
    completed = subprocess.run(
        [str(script), '--remote', 'missing-fixture-remote'],
        cwd=mock_repository,
        check=False,
        capture_output=True,
        text=True,
    )

    # Assert
    assert (completed.returncode, completed.stdout.splitlines()[-1]) == (
        6,
        'RESULT=FETCH_FAILED',
    )
