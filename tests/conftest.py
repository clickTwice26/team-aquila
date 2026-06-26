"""Shared pytest fixtures."""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from queuestorm.main import app

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAMPLES = os.path.join(_ROOT, "contexts", "SUST_Preli_Sample_Cases.json")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_pack() -> dict:
    with open(_SAMPLES, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def sample_cases(sample_pack) -> list:
    return sample_pack["cases"]
