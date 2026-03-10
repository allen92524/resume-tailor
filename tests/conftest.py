"""Shared fixtures for resume-tailor tests."""

import json
import os

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _load_json_fixture(filename: str) -> dict:
    return json.loads(_load_fixture(filename))


@pytest.fixture
def sample_resume() -> str:
    return _load_fixture("sample_resume.txt")


@pytest.fixture
def sample_jd() -> str:
    return _load_fixture("sample_jd.txt")


@pytest.fixture
def sample_reference_resume() -> str:
    return _load_fixture("sample_reference_resume.txt")


@pytest.fixture
def mock_jd_analysis() -> dict:
    return _load_json_fixture("mock_jd_analysis.json")


@pytest.fixture
def mock_resume_generation() -> dict:
    return _load_json_fixture("mock_resume_generation.json")


@pytest.fixture
def mock_gap_analysis() -> dict:
    return _load_json_fixture("mock_gap_analysis.json")


@pytest.fixture
def mock_compatibility() -> dict:
    return _load_json_fixture("mock_compatibility.json")


@pytest.fixture
def mock_review() -> dict:
    return _load_json_fixture("mock_review.json")
