"""A fake Docker host for the deploy scripts: a temp install directory, a fake `docker` (and
`systemctl`) first on PATH, and helpers to read what the scripts left behind."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DEPLOY = REPO / "deploy"
FAKE_DOCKER = Path(__file__).with_name("fake_docker.py")


class Host:
    def __init__(self, root: Path):
        self.dir = root / "opt"
        self.bin = root / "bin"
        self.units = root / "units"
        self.state_file = root / "docker.json"
        self.prefix: list[str] = []  # e.g. ["unshare", "-r"] to run as a mapped root
        for d in (self.dir, self.bin, self.units):
            d.mkdir()
        (self.bin / "docker").write_text(f'#!/bin/sh\nexec "{os.sys.executable}" "{FAKE_DOCKER}" "$@"\n')
        (self.bin / "systemctl").write_text(f'#!/bin/sh\necho "$@" >> "{root}/systemctl-calls"\n')
        for f in ("docker", "systemctl"):
            (self.bin / f).chmod(0o755)
        self.docker = {"registry": {}, "local": {}, "unhealthy": [], "pull_fail": False, "running": None, "calls": []}
        self.save_docker()

    # ---- fake docker state
    def save_docker(self):
        self.state_file.write_text(json.dumps(self.docker))

    def load_docker(self) -> dict:
        self.docker = json.loads(self.state_file.read_text())
        return self.docker

    def release(self, *versions, latest=None):
        """Publish versions on the fake registry; `latest` points at the newest unless given."""
        for v in versions:
            self.docker["registry"][v] = v
        self.docker["registry"]["latest"] = latest or versions[-1]
        self.save_docker()

    # ---- install dir
    def env(self, **values):
        lines = [f"{k}={v}" for k, v in values.items()]
        (self.dir / ".env").write_text("\n".join(lines) + "\n")

    def env_get(self, key):
        for line in (self.dir / ".env").read_text().splitlines():
            if line.startswith(key + "="):
                value = line.split("=", 1)[1]
        return value

    @property
    def updater(self) -> Path:
        return self.dir / "updater"

    def status(self) -> dict:
        return json.loads((self.updater / "status.json").read_text())

    def run(self, script: str, *args, env=None) -> subprocess.CompletedProcess:
        e = {"PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_DOCKER_STATE": str(self.state_file),
             "FAKE_DEPLOY_SRC": str(DEPLOY), "SYSTEMD_UNIT_DIR": str(self.units), "HOME": str(self.dir)}
        e.update(env or {})
        cmd = [*self.prefix, "bash", str(self.dir / script), *args]
        return subprocess.run(cmd, env=e, capture_output=True, text=True, timeout=120)

    def install(self, *names):
        for n in names:
            shutil.copy(DEPLOY / n, self.dir / n)


@pytest.fixture
def host(tmp_path) -> Host:
    if shutil.which("flock") is None:
        pytest.skip("flock (util-linux) is not installed")
    return Host(tmp_path)
