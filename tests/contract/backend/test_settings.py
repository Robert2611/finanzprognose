import pytest

from app.settings import Settings


@pytest.mark.contract("SETTINGS-001")
def test_string_variables_are_copied_verbatim():
    """SETTINGS-001: path, time and credential variables map 1:1 onto the fields."""
    s = Settings.from_env({"DB_PATH": "/x/db.sqlite", "BACKUP_DIR": "/nas", "BACKUP_TIME": "04:30",
                           "APP_USER": "robert", "APP_PASSWORD": "pw"})
    assert (s.db_path, s.backup_dir, s.backup_time, s.app_user, s.app_password) == \
        ("/x/db.sqlite", "/nas", "04:30", "robert", "pw")


@pytest.mark.contract("SETTINGS-002")
@pytest.mark.parametrize("value,expected", [("0", False), ("1", True), (None, True)])
def test_flag_variables(value, expected):
    """SETTINGS-002: BACKUP_REQUIRE_MARKER / BACKUP_SCHEDULER are on unless set to 0."""
    env = {} if value is None else {"BACKUP_REQUIRE_MARKER": value, "BACKUP_SCHEDULER": value}
    s = Settings.from_env(env)
    assert s.backup_require_marker is expected
    assert s.backup_scheduler is expected


@pytest.mark.contract("SETTINGS-003")
def test_unset_variables_fall_back_to_defaults():
    """SETTINGS-003: an empty environment gives the dataclass defaults."""
    assert Settings.from_env({}) == Settings()
    assert Settings.from_env({"DB_PATH": "/x/db.sqlite"}) == Settings(db_path="/x/db.sqlite")


@pytest.mark.contract("SETTINGS-004")
def test_version_and_update_dir():
    """SETTINGS-004: APP_VERSION / UPDATE_DIR are copied; unset they are "dev" and ""."""
    s = Settings.from_env({"APP_VERSION": "v1.4.0", "UPDATE_DIR": "/updater"})
    assert (s.app_version, s.update_dir) == ("v1.4.0", "/updater")
    d = Settings.from_env({})
    assert (d.app_version, d.update_dir) == ("dev", "")
