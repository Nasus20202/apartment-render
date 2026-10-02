"""Shared fixtures. Scripts that need Blender (bpy) are not imported here; only plain-Python modules."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    return json.loads((ROOT / "data" / f"{name}.json").read_text())


@pytest.fixture(scope="session")
def floorplan():
    return load("floorplan")


@pytest.fixture(scope="session")
def furniture():
    return load("furniture")


@pytest.fixture(scope="session")
def items(furniture):
    return furniture["items"]


@pytest.fixture(scope="session")
def lighting():
    return load("lighting")


@pytest.fixture(scope="session")
def electrical():
    return load("electrical")
