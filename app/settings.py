"""Runtime configuration, held per app instance.

`Settings.from_env()` reads the environment variables documented in the README and
`.env.example`; that is what production (`uvicorn app.main:app`) uses. Tests build a
`Settings` directly and pass it to `main.create_app()`, so several apps with different
configurations (auth on/off, other DB, other backup dir) can live in one process.
Nothing in the app reads these environment variables anywhere else.
"""
import os
from dataclasses import dataclass
from typing import Mapping

from fastapi import Request


@dataclass(frozen=True)
class Settings:
    db_path: str = "/data/finanzen.sqlite"
    backup_dir: str = "/backup"
    backup_time: str = "03:00"            # HH:MM, local time
    backup_require_marker: bool = True    # refuse to back up without BACKUP_DIR/.nas-marker
    backup_scheduler: bool = True         # start the daily backup thread in the lifespan
    app_user: str = "admin"
    app_password: str = ""                # empty disables auth
    app_version: str = "dev"              # release tag baked into the image (Dockerfile ARG APP_VERSION)
    update_dir: str = ""                  # folder shared with the host updater (B-026); empty = none

    @property
    def status_file(self) -> str:
        """Backup status lives next to the database, not on the NAS."""
        return os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "backup_status.json")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        d = cls()
        return cls(
            db_path=env.get("DB_PATH", d.db_path),
            backup_dir=env.get("BACKUP_DIR", d.backup_dir),
            backup_time=env.get("BACKUP_TIME", d.backup_time),
            backup_require_marker=env.get("BACKUP_REQUIRE_MARKER", "1") == "1",
            backup_scheduler=env.get("BACKUP_SCHEDULER", "1") == "1",
            app_user=env.get("APP_USER", d.app_user),
            app_password=env.get("APP_PASSWORD", d.app_password),
            app_version=env.get("APP_VERSION", d.app_version),
            update_dir=env.get("UPDATE_DIR", d.update_dir),
        )


def get_settings(request: Request) -> Settings:
    """FastAPI dependency: the settings of the app serving this request."""
    return request.app.state.settings
