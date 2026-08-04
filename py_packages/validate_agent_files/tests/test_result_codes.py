#!/usr/bin/env python3

"""Behavior tests for the shared skill-script result-code helper."""

from __future__ import annotations

from pathlib import Path
import signal
import subprocess


def test_canonical_result_codes_report_failure_when_interrupted() -> None:
    """Report a failure result when a signal interrupts the canonical helper."""
    # Arrange
    repository_root = Path(__file__).resolve().parents[3]
    result_codes = (
        repository_root / '.agents/plugins/agentdev/skills/skill-scripts/assets/result-codes.sh'
    )
    outcomes: dict[str, tuple[int, str]] = {}

    # Act
    for interrupt_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        process = subprocess.Popen(
            [
                'bash',
                '-c',
                'source "$1"; printf "READY\\n" >&2; while :; do :; done',
                'bash',
                str(result_codes),
            ],
            cwd=repository_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stderr is not None
            assert process.stderr.readline() == 'READY\n'
            process.send_signal(interrupt_signal)
            stdout, _ = process.communicate(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        assert process.returncode is not None
        outcomes[interrupt_signal.name] = (process.returncode, stdout)

    # Assert
    assert outcomes == {
        interrupt_signal.name: (1, 'RESULT=SCRIPT_FAILURE\n')
        for interrupt_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    }
