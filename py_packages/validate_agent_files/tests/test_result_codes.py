#!/usr/bin/env python3

"""Behavior tests for the shared skill-script result-code helper."""

from __future__ import annotations

from pathlib import Path
import signal
import subprocess


def test_canonical_result_codes_preserve_terminating_signals() -> None:
    """Name terminating signals while preserving their shell exit statuses."""
    # Arrange
    repository_root = Path(__file__).resolve().parents[3]
    result_codes = (
        repository_root / '.agents/plugins/agentdev/skills/skill-scripts/assets/result-codes.sh'
    )
    outcomes: dict[str, tuple[int, int, str]] = {}

    # Act
    for interrupt_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        process = subprocess.run(
            [
                'bash',
                '-c',
                'source "$1"; kill -s "$2" "$$"',
                'bash',
                str(result_codes),
                interrupt_signal.name,
            ],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        shell_status = 128 - process.returncode if process.returncode < 0 else process.returncode
        outcomes[interrupt_signal.name] = (
            process.returncode,
            shell_status,
            process.stdout,
        )

    # Assert
    assert outcomes == {
        signal.SIGHUP.name: (-signal.SIGHUP, 129, 'RESULT=SIGNAL_HUP\n'),
        signal.SIGINT.name: (-signal.SIGINT, 130, 'RESULT=SIGNAL_INT\n'),
        signal.SIGTERM.name: (-signal.SIGTERM, 143, 'RESULT=SIGNAL_TERM\n'),
    }
