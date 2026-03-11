"""Tests for profile.py."""

import json
import os
from unittest.mock import patch

import pytest

from src.profile import (
    load_profile,
    save_profile,
    lookup_experience,
    save_experience,
    get_preferences,
    save_preferences,
    append_history,
    delete_profile,
    export_as_markdown,
    extract_identity,
    create_profile,
    backup_profile,
    list_backups,
    restore_profile,
)
from src.models import Profile, Identity


@pytest.fixture
def profile_dir(tmp_path):
    """Redirect profile storage to a temp directory."""
    profile_path = tmp_path / "profile.json"
    with patch("src.profile.get_profile_dir", return_value=str(tmp_path)), patch(
        "src.profile.get_profile_path", return_value=str(profile_path)
    ), patch("src.profile._migrate_legacy_profile"):
        yield tmp_path, str(profile_path)


@pytest.fixture
def sample_profile():
    return Profile(
        identity=Identity(
            name="Sarah Chen",
            email="sarah.chen@email.com",
            phone="(415) 555-0198",
            location="Seattle, WA",
            linkedin="linkedin.com/in/sarahchen",
            github="github.com/sarahchen",
        ),
        base_resume="Sarah Chen\nStaff Software Engineer...",
        experience_bank={
            "Go": "I've written several CLI tools in Go and completed the Go tour",
            "Terraform": "Used Terraform to manage AWS infrastructure for 2 years",
        },
        history=[],
        preferences={},
    )


class TestLoadSaveProfile:
    def test_load_returns_none_when_no_file(self, profile_dir):
        assert load_profile() is None

    def test_save_and_load(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        loaded = load_profile()
        assert isinstance(loaded, Profile)
        assert loaded.identity.name == "Sarah Chen"
        assert loaded.updated_at is not None

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        profile_path = nested / "profile.json"
        with patch("src.profile.get_profile_dir", return_value=str(nested)), patch(
            "src.profile.get_profile_path", return_value=str(profile_path)
        ):
            prof = Profile(identity=Identity(name="Test"))
            save_profile(prof)
            assert os.path.isfile(str(profile_path))


class TestExperienceBank:
    def test_lookup_existing(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        assert lookup_experience(sample_profile, "Go") is not None
        assert "CLI tools" in lookup_experience(sample_profile, "Go")

    def test_lookup_case_insensitive(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        assert lookup_experience(sample_profile, "go") is not None
        assert lookup_experience(sample_profile, "GO") is not None

    def test_lookup_missing(self, sample_profile):
        assert lookup_experience(sample_profile, "Rust") is None

    def test_save_experience(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        save_experience(sample_profile, "gRPC", "Built 3 gRPC services")
        assert sample_profile.experience_bank["gRPC"] == "Built 3 gRPC services"

    def test_save_experience_adds_to_bank(self, profile_dir):
        profile = Profile(identity=Identity(name="Test"))
        save_profile(profile)
        save_experience(profile, "Python", "10 years")
        assert profile.experience_bank["Python"] == "10 years"


class TestHistory:
    def test_append_history(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        append_history(
            sample_profile,
            "Meridian",
            "Senior Platform Engineer",
            78,
            "/output/resume.docx",
        )
        assert len(sample_profile.history) == 1
        entry = sample_profile.history[0]
        assert entry["company"] == "Meridian"
        assert entry["role"] == "Senior Platform Engineer"
        assert entry["match_score"] == 78

    def test_append_multiple_history(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        append_history(sample_profile, "Company A", "Role A", 80, "/a.docx")
        append_history(sample_profile, "Company B", "Role B", 60, "/b.docx")
        assert len(sample_profile.history) == 2


class TestPreferences:
    def test_get_preferences_empty(self, sample_profile):
        assert get_preferences(sample_profile) == {}

    def test_save_and_get_preferences(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        save_preferences(sample_profile, "pdf", "/custom/output")
        prefs = get_preferences(sample_profile)
        assert prefs["format"] == "pdf"
        assert prefs["output_path"] == "/custom/output"


class TestDeleteProfile:
    def test_delete_existing(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        _, profile_path = profile_dir
        assert os.path.isfile(profile_path)
        assert delete_profile() is True
        assert not os.path.isfile(profile_path)

    def test_delete_nonexistent(self, profile_dir):
        assert delete_profile() is False


class TestExportAsMarkdown:
    def test_export_has_name(self, sample_profile):
        md = export_as_markdown(sample_profile)
        assert "# Sarah Chen" in md

    def test_export_has_contact(self, sample_profile):
        md = export_as_markdown(sample_profile)
        assert "sarah.chen@email.com" in md

    def test_export_has_experience_bank(self, sample_profile):
        md = export_as_markdown(sample_profile)
        assert "Experience Bank" in md
        assert "Go" in md

    def test_export_with_history(self, sample_profile):
        sample_profile.history = [
            {
                "date": "2026-03-01T00:00:00Z",
                "company": "TestCo",
                "role": "Engineer",
                "match_score": 85,
            },
        ]
        md = export_as_markdown(sample_profile)
        assert "TestCo" in md
        assert "85%" in md


class TestProfileNewFields:
    def test_writing_preferences_roundtrip(self, profile_dir):
        profile = Profile(
            identity=Identity(name="Test"),
            writing_preferences={"tone": "formal", "bullet_length": "shorter"},
        )
        save_profile(profile)
        loaded = load_profile()
        assert loaded.writing_preferences["tone"] == "formal"
        assert loaded.writing_preferences["bullet_length"] == "shorter"

    def test_applications_since_review_roundtrip(self, profile_dir):
        profile = Profile(
            identity=Identity(name="Test"),
            applications_since_review=5,
        )
        save_profile(profile)
        loaded = load_profile()
        assert loaded.applications_since_review == 5

    def test_original_resume_roundtrip(self, profile_dir):
        profile = Profile(
            identity=Identity(name="Test"),
            base_resume="Improved version",
            original_resume="Original version",
        )
        save_profile(profile)
        loaded = load_profile()
        assert loaded.base_resume == "Improved version"
        assert loaded.original_resume == "Original version"

    def test_migration_copies_base_to_original(self, profile_dir):
        """When loading a profile without original_resume, it should be migrated."""
        _, profile_path = profile_dir
        # Write a profile without original_resume field
        data = {
            "identity": {"name": "Test"},
            "base_resume": "My resume text",
            "experience_bank": {},
            "history": [],
            "preferences": {},
        }
        with open(profile_path, "w") as f:
            json.dump(data, f)

        loaded = load_profile()
        assert loaded.original_resume == "My resume text"

    def test_migration_does_not_overwrite_existing_original(self, profile_dir):
        """If original_resume already exists, migration should not change it."""
        profile = Profile(
            identity=Identity(name="Test"),
            base_resume="Improved",
            original_resume="Original",
        )
        save_profile(profile)
        loaded = load_profile()
        assert loaded.original_resume == "Original"


class TestExtractIdentity:
    def test_extract_identity_mocked(self, sample_resume):
        mock_identity = {
            "name": "Sarah Chen",
            "email": "sarah.chen@email.com",
            "phone": "(415) 555-0198",
            "location": "Seattle, WA",
            "linkedin": "linkedin.com/in/sarahchen",
            "github": "github.com/sarahchen",
        }

        with patch("src.profile.call_llm", return_value=json.dumps(mock_identity)):
            result = extract_identity(sample_resume)

        assert isinstance(result, Identity)
        assert result.name == "Sarah Chen"
        assert result.email == "sarah.chen@email.com"


class TestBackupProfile:
    def test_backup_creates_file(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        backup_path = backup_profile()
        assert backup_path is not None
        assert os.path.isfile(backup_path)
        assert "profile_backup_" in os.path.basename(backup_path)

    def test_backup_contains_same_data(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        backup_path = backup_profile()
        with open(backup_path, "r") as f:
            backup_data = json.load(f)
        assert backup_data["identity"]["name"] == "Sarah Chen"

    def test_backup_no_profile(self, profile_dir):
        assert backup_profile() is None

    def test_backup_overwrites_same_day(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        path1 = backup_profile()
        path2 = backup_profile()
        assert path1 == path2
        assert len(list_backups()) == 1


class TestListBackups:
    def test_list_empty(self, profile_dir):
        assert list_backups() == []

    def test_list_after_backup(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        backup_profile()
        backups = list_backups()
        assert len(backups) == 1

    def test_list_sorted(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        tmp_dir, _ = profile_dir
        # Create fake backups with different dates
        for date in ["2026-01-01", "2026-03-01", "2026-02-01"]:
            path = tmp_dir / f"profile_backup_{date}.json"
            path.write_text("{}")
        backups = list_backups()
        names = [os.path.basename(b) for b in backups]
        assert names == sorted(names)


class TestRestoreProfile:
    def test_restore_overwrites_current(self, profile_dir, sample_profile):
        save_profile(sample_profile)
        backup_path = backup_profile()

        # Modify the current profile
        sample_profile.identity.name = "Modified Name"
        save_profile(sample_profile)

        # Restore from backup
        restore_profile(backup_path)
        loaded = load_profile()
        assert loaded.identity.name == "Sarah Chen"

    def test_restore_creates_profile_dir(self, tmp_path):
        nested = tmp_path / "new" / "dir"
        profile_path = nested / "profile.json"
        backup_src = tmp_path / "backup.json"
        backup_src.write_text('{"identity": {"name": "Test"}}')

        with patch("src.profile.get_profile_dir", return_value=str(nested)), patch(
            "src.profile.get_profile_path", return_value=str(profile_path)
        ):
            restore_profile(str(backup_src))
            assert os.path.isfile(str(profile_path))


class TestCreateProfile:
    def test_create_profile(self, profile_dir, sample_resume):
        mock_identity = {
            "name": "Sarah Chen",
            "email": "sarah.chen@email.com",
            "phone": None,
            "location": "Seattle, WA",
            "linkedin": None,
            "github": None,
        }

        with patch("src.profile.call_llm", return_value=json.dumps(mock_identity)):
            profile = create_profile(sample_resume)

        assert isinstance(profile, Profile)
        assert profile.identity.name == "Sarah Chen"
        assert profile.base_resume == sample_resume
        assert profile.experience_bank == {}
        assert profile.history == []

    def test_create_profile_stores_original_resume(self, profile_dir, sample_resume):
        mock_identity = {
            "name": "Sarah Chen",
            "email": "sarah.chen@email.com",
            "phone": None,
            "location": None,
            "linkedin": None,
            "github": None,
        }

        with patch("src.profile.call_llm", return_value=json.dumps(mock_identity)):
            profile = create_profile(
                sample_resume,
                original_resume_text="Original unmodified resume text",
            )

        assert profile.base_resume == sample_resume
        assert profile.original_resume == "Original unmodified resume text"

    def test_create_profile_defaults_original_to_base(self, profile_dir, sample_resume):
        mock_identity = {
            "name": "Sarah Chen",
            "email": None,
            "phone": None,
            "location": None,
            "linkedin": None,
            "github": None,
        }

        with patch("src.profile.call_llm", return_value=json.dumps(mock_identity)):
            profile = create_profile(sample_resume)

        assert profile.original_resume == sample_resume
