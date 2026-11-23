# settings — runtime configuration from environment variables
ID prefix: SETTINGS
Layer: backend

## Purpose
Turns the environment variables of a production deployment into the per-app `Settings`
object, so nothing else in the app reads the environment.

## Interface
`Settings.from_env(env: Mapping[str, str] = os.environ) -> Settings` (`app/settings.py`).
`Settings` is a frozen dataclass with the fields `db_path`, `backup_dir`, `backup_time`,
`backup_require_marker`, `backup_scheduler`, `app_user`, `app_password` (defaults in
`ENVIRONMENT.md` §2).

## Dependencies & side effects
Reads only the mapping it is given. No files, no DB.

## Behavior clauses

- `SETTINGS-001` [TEST] `DB_PATH`, `BACKUP_DIR`, `BACKUP_TIME`, `APP_USER` and
  `APP_PASSWORD` are copied verbatim into `db_path`, `backup_dir`, `backup_time`,
  `app_user` and `app_password`.
- `SETTINGS-002` [TEST] `BACKUP_REQUIRE_MARKER=0` and `BACKUP_SCHEDULER=0` turn
  `backup_require_marker` and `backup_scheduler` off; `1` (or leaving them unset) keeps
  them on.
- `SETTINGS-003` [TEST] A variable that is not set falls back to the dataclass default, so
  `Settings.from_env({}) == Settings()`.

## Examples
- `{"DB_PATH": "/x/db.sqlite", "BACKUP_SCHEDULER": "0"}` → `db_path="/x/db.sqlite"`,
  `backup_scheduler=False`, everything else default.

## Out of scope / not specified
- Validation of the values (e.g. a malformed `BACKUP_TIME`); `from_env` does none.
- Flag values other than `0` and `1`.

## Open questions
None.
