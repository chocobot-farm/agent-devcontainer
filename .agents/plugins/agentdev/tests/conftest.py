#!/usr/bin/env python3

"""
Shared fixtures for the plugin's own script tests.

These tests exercise the scripts this plugin ships — the helpers in ``bin/`` and
the ``scripts/`` bundled with individual skills. They resolve everything from the
plugin root so the suite runs unchanged from a consumer's plugin cache, where the
repository that develops the plugin is not present.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

import pytest


@pytest.fixture
def plugin_root() -> Path:
    """Resolve the plugin root that ships the scripts under test."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin_tmp_path(plugin_root: Path):
    """Create an isolated temporary directory inside the plugin tree."""
    temp_path = plugin_root / '.tmp' / f'pytest-{uuid4().hex}'
    temp_path.mkdir(parents=True)
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path)
