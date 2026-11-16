"""Shared fixtures and plumbing for the black-box contract suite.

Everything goes through the documented interface: ``create_app(Settings(...))`` + ``TestClient``,
``app.db`` / ``app.backup`` / ``app.forecast`` / ``app.schemas`` functions, plain ``sqlite3`` on
database/backup files, and (for Playwright) the same app served by an in-process uvicorn thread.
Each test gets its own temp DB, status file and NAS directory, so tests are independent.
"""
import json
import itertools
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

from tests.contract.helpers.clauses import known_ids
from tests.contract.helpers.nas import Nas
from tests.contract.helpers.seed import Seed
from tests.contract.helpers.server import LiveServer

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.json"
BROWSER_FIXTURES = {"page", "context", "browser", "live_server"}


# --------------------------------------------------------------------------- options & markers

def pytest_addoption(parser):
    parser.addoption("--contract", action="append", default=[], metavar="ID",
                     help="run only tests that verify this contract clause ID (repeatable)")


def _contract_ids(item) -> list[str]:
    ids: list[str] = []
    for m in item.iter_markers("contract"):
        ids.extend(m.args)
    return ids


def _in_suite(item) -> bool:
    return HERE in Path(str(item.fspath)).parents


def pytest_collection_modifyitems(config, items):
    known = known_ids()
    wanted = set(config.getoption("--contract"))
    selected, deselected = [], []
    problems = []
    for item in items:
        if not _in_suite(item):
            selected.append(item)
            continue
        ids = _contract_ids(item)
        is_harness = "harness" in Path(str(item.fspath)).relative_to(HERE).parts
        if not ids and not is_harness:
            problems.append(f"{item.nodeid}: missing @pytest.mark.contract(...)")
        for cid in ids:
            if cid not in known:
                problems.append(f"{item.nodeid}: unknown clause ID {cid!r} (not in contracts/TRACEABILITY.md)")
        if BROWSER_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.browser)
        (selected if not wanted or wanted & set(ids) else deselected).append(item)
    if problems:
        raise pytest.UsageError("contract marker problems:\n  " + "\n  ".join(problems))
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


# --------------------------------------------------------------------------- result recording

class _Recorder:
    def __init__(self):
        self.ids: dict[str, list[str]] = {}
        self.results: list[dict] = []

    def pytest_collection_modifyitems(self, items):
        for item in items:
            if _in_suite(item):
                self.ids[item.nodeid] = _contract_ids(item)

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.ids:
            return
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            outcome = report.outcome
            if hasattr(report, "wasxfail"):
                outcome = "xfailed" if report.skipped else "xpassed"
            reason = ""
            if report.skipped and isinstance(report.longrepr, tuple):
                reason = str(report.longrepr[2])
            elif report.failed:
                # only the exception message: never traceback source lines
                crash = getattr(report.longrepr, "reprcrash", None)
                reason = (crash.message if crash else "failed")[:1500]
            self.results.append({"nodeid": report.nodeid, "clauses": self.ids[report.nodeid],
                                 "outcome": outcome, "reason": reason})

    def pytest_sessionfinish(self, session):
        if self.results and not session.config.getoption("--contract"):
            RESULTS.write_text(json.dumps(self.results, indent=1), encoding="utf-8")


def pytest_configure(config):
    config.pluginmanager.register(_Recorder(), "contract-recorder")


# --------------------------------------------------------------------------- settings & apps

def _marker_overrides(request) -> dict:
    over: dict = {}
    for m in request.node.iter_markers("app_settings"):
        over.update(m.kwargs)
    return over


@pytest.fixture
def make_settings(tmp_path):
    """Factory: a fresh, isolated Settings (own DB dir + own NAS dir) per call."""
    counter = itertools.count()

    def make(**overrides) -> Settings:
        base = tmp_path / f"app{next(counter)}"
        nas = base / "nas"
        nas.mkdir(parents=True, exist_ok=True)
        values = dict(db_path=str(base / "data" / "finanzen.sqlite"), backup_dir=str(nas),
                      backup_require_marker=True, backup_scheduler=False, app_password="")
        values.update(overrides)
        return Settings(**values)

    return make


@pytest.fixture
def settings(make_settings, request) -> Settings:
    """The primary app's settings (override per test with @pytest.mark.app_settings(...))."""
    return make_settings(**_marker_overrides(request))


@pytest.fixture
def nas(settings) -> Nas:
    """The primary app's NAS directory (exists, no marker yet)."""
    n = Nas(Path(settings.backup_dir)).create()
    yield n
    n.restore_permissions()


@pytest.fixture
def db_path(settings) -> str:
    """Path of the primary app's database file (the app creates it on startup / db.init)."""
    return settings.db_path


@pytest.fixture
def fresh_db(db_path):
    """An empty database created by db.init(path) (no app involved)."""
    from app import db
    db.init(db_path)
    return db_path


@pytest.fixture
def make_client(request):
    """Factory: start an app from Settings and return a TestClient (lifespan running)."""
    stack = []

    def make(s: Settings, **client_kw) -> TestClient:
        tc = TestClient(create_app(s), **client_kw)
        tc.__enter__()
        stack.append(tc)
        return tc

    yield make
    for tc in reversed(stack):
        tc.__exit__(None, None, None)


@pytest.fixture
def client(make_client, settings, nas) -> TestClient:
    """TestClient for the primary app. Sends Basic credentials automatically if a password is set."""
    kw = {}
    if settings.app_password:
        kw["auth"] = (getattr(settings, "app_user", "admin"), settings.app_password)
    tc = make_client(settings)
    if kw:
        tc.auth = kw["auth"]
    return tc


@pytest.fixture
def anon_client(make_client, settings, nas) -> TestClient:
    """TestClient for the primary app that never sends credentials."""
    return make_client(settings)


@pytest.fixture
def seed(client) -> Seed:
    return Seed(client)


# --------------------------------------------------------------------------- browser

@pytest.fixture
def live_server(settings, nas):
    """The primary app served on a real local port (Playwright). No subprocess, no env vars."""
    srv = LiveServer(create_app(settings)).start()
    yield srv
    srv.stop()


@pytest.fixture
def context(browser, live_server, request):
    """A fresh browser context per test, pointed at this test's app (``page.goto('/')``).

    Overrides pytest-playwright's ``context`` (whose options are session-scoped). Extra context
    options, e.g. Basic-auth credentials, via ``@pytest.mark.browser_context(http_credentials={...})``.
    """
    opts = {"base_url": live_server.url, "locale": "de-DE", "timezone_id": "Europe/Berlin"}
    for m in request.node.iter_markers("browser_context"):
        opts.update(m.kwargs)
    ctx = browser.new_context(**opts)
    ctx.set_default_timeout(10_000)
    yield ctx
    ctx.close()


@pytest.fixture
def seed_live(live_server):
    """Seed builders for a live server (httpx client; same public API)."""
    import httpx
    s = live_server._server.config.app.state.settings
    auth = (getattr(s, "app_user", "admin"), s.app_password) if s.app_password else None
    with httpx.Client(base_url=live_server.url, auth=auth) as c:
        yield Seed(c)
