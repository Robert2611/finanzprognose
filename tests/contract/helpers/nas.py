"""A local temp directory standing in for the NAS (BACKUP_DIR)."""
import os
import shutil
import stat
from pathlib import Path

MARKER = ".nas-marker"


class Nas:
    def __init__(self, path: Path):
        self.path = Path(path)

    def create(self) -> "Nas":
        self.path.mkdir(parents=True, exist_ok=True)
        return self

    def put_marker(self) -> None:
        self.create()
        (self.path / MARKER).write_text("")

    def remove_marker(self) -> None:
        (self.path / MARKER).unlink(missing_ok=True)

    def remove(self) -> None:
        """Make the target unreachable: the directory does not exist."""
        self.restore_permissions()
        shutil.rmtree(self.path, ignore_errors=True)

    def make_read_only(self) -> None:
        """Permission denied: the process can list/read but not create files."""
        os.chmod(self.path, stat.S_IRUSR | stat.S_IXUSR)

    def restore_permissions(self) -> None:
        if self.path.exists():
            os.chmod(self.path, stat.S_IRWXU)

    def names(self) -> list[str]:
        return sorted(p.name for p in self.path.iterdir()) if self.path.exists() else []

    def backups(self, suffix: str = ".sqlite") -> list[str]:
        return [n for n in self.names() if n.startswith("finanzen_") and n.endswith(suffix)]
