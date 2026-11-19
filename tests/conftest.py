from __future__ import annotations

import os

import pymupdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def own_config(tmp_path, monkeypatch):
    """A configuration folder of its own, so the tests don't read or change the user's."""
    monkeypatch.setenv("PY_ANNOTATE_CONFIG", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from py_annotate import interface

    interface.use(None)


@pytest.fixture(autouse=True)
def pages_here(monkeypatch):
    """Pages rendered in the tests' own process, at once (a test may turn this off)."""
    from py_annotate.gui import renderer

    monkeypatch.setattr(renderer, "ENABLED", False)


@pytest.fixture
def sample(tmp_path):
    """A PDF of 3 pages (595 × 842 points), with two lines of text on each; the
    third page is turned 90 degrees."""
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 100), f"First line of page {i + 1}", fontsize=14)
        page.insert_text((72, 130), "A second line of text", fontsize=14)
        if i == 2:
            page.set_rotation(90)
    doc.save(path)
    return path
