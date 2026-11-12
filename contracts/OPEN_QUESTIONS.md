# Open Questions

Ambiguities, under-specified behavior, and suspected bugs found while writing the contracts.
Each entry: the related clause(s), what was observed, why it's unclear/suspicious, and the
options. **Suspected bugs are marked.** The test-writing agent should treat the linked
clauses as not-yet-settled (write them `xfail`/skipped until resolved).

---

### 1. (reserved)
Intentionally left blank to keep numbering stable with the contract cross-references.

### 2. No-op update writes no audit row and does not advance `data_version`
- **Clauses:** `DB-CRUD-010`, `DB-CRUD-014`, `DB-AUDIT-012`, `API-RES-011`.
- **Observed:** An `update` where every submitted value already equals the stored value
  returns the row unchanged, does **not** bump `updated_at`, and writes **no** `audit_log`
  row — so `data_version` (MAX audit id) is unchanged. Same for archiving an already-archived
  row.
- **Why unclear:** This is defensible (don't log non-changes), but it has side effects: a
  "save" that happened to change nothing silently produces no audit trail, and a backup that
  keys off `data_version` will treat the state as unchanged. Is "a save that changed nothing
  is a no-event" the intended contract?
- **Options:** (a) keep as-is (document it), (b) always log an update even when nothing
  changed, (c) log only when something changed but still bump a change counter.

### 3. Archive/restore are not optimistic-locked — *possible bug*
- **Clauses:** `DB-CRUD-013`, `API-RES-018`, `API-RES-003`.
- **Observed:** `set_archived` takes no `expected_updated_at`; archive/restore always apply,
  overwriting whatever the current state is, with no 409 conflict path.
- **Why suspicious:** Updates are carefully optimistic-locked to prevent silent overwrites
  (a headline data-safety promise), but archive/restore bypass that. Two tabs could archive/
  restore in a way the user doesn't expect.
- **Options:** (a) intended — archive/restore are idempotent flips, locking adds little;
  (b) bug — they should honor `expected_updated_at` like updates.

### 4. Revert of a `revert` row is unspecified
- **Clauses:** `DB-AUDIT` (out-of-scope note), `API-AUDIT-007`.
- **Observed:** `revert` can target any audit row, including a previous `revert`. The code
  path would restore that revert row's `before` snapshot.
- **Why unclear:** The resulting chain (redo? re-undo?) is not defined anywhere and could
  confuse users.
- **Options:** define and document the semantics, or disallow reverting a `revert`.

### 5. Schema does not couple `adjustments.mode` to which of `amount`/`percent` is set
- **Clauses:** `DATA-015`, `SCH-015`, `SCH-016`.
- **Observed:** The API models null the irrelevant field, but the DB has no CHECK enforcing
  it. A write bypassing the API could store an inconsistent row (`mode='set'` with a
  `percent`).
- **Why unclear:** Is the invariant meant to be DB-enforced or API-only? Only matters if
  anything ever writes outside the API (forbidden by the data-safety rules, so maybe fine).
- **Options:** add a CHECK constraint, or accept API-only enforcement and document it.

### 6. Account with no (non-archived) checkpoint — behavior & messaging
- **Clauses:** `FC-011`, `E2E-CP-005`, `E2E-CP-006`.
- **Observed:** Such an account yields a `no_checkpoint` warning and null opening/closing; its
  bookings never apply (they're all "before the first checkpoint", of which there is none).
- **Why unclear:** This is a reasonable "can't forecast without an anchor" rule, but it's only
  evident from behavior. Confirm it's intended that **all** of the account's bookings are
  dropped (not, say, counted from 0).
- **Options:** confirm as intended, or define a zero-based fallback.

### 7. Transfer to an archived target account is silently dropped (both sides) — *review*
- **Clauses:** `FC-028`, `E2E-BOOK` (transfer), `FC-011`.
- **Observed:** If a transfer entry's `to_account_id` is an archived account, the **entire**
  entry is skipped — no item on the source side either — with only a `transfer_target_archived`
  warning.
- **Why suspicious:** The money "leaving" the source account just vanishes from the forecast.
  A user might expect the outflow to still show (or the transfer to be blocked at archive
  time). See also #10.
- **Options:** (a) intended — drop both sides and warn; (b) keep the source outflow; (c)
  prevent archiving an account that is a transfer target.

### 8. Forecast `start` month regex allows out-of-range months — *possible bug*
- **Clauses:** `API-FC-007`, `FC` (out-of-scope note).
- **Observed:** `start` is validated only against `^\d{4}-\d{2}$`, so `2026-13` or `2026-00`
  pass. The engine's month arithmetic then **silently wraps** them (`2026-13` → `2027-01`,
  `2026-00` → `2025-12`) instead of rejecting or honoring them literally.
- **Why suspicious:** A client sending a bad month gets a plausible-looking but shifted
  forecast with no error.
- **Options:** (a) validate `01`–`12` and return 422; (b) document the wrap as intended.

### 9. archive/restore unknown-table error shape differs from create/update
- **Clauses:** `API-RES-002`, `API-RES-015`.
- **Observed:** `POST/PUT /api/{table}` for an unknown table returns the `{code:'unknown_table',
  params:{table}}` envelope (404). The archive/restore routes instead return a bare 404 with
  no `{code}` envelope for an unknown table.
- **Why unclear:** Inconsistent error contract for the "unknown table" case across endpoints.
- **Options:** make archive/restore emit the same `unknown_table` envelope.

### 10. Archiving an account referenced by active entries/checkpoints has no guard/cascade
- **Clauses:** `API-RES-020`, `FC-028`.
- **Observed:** An account can be archived while entries/checkpoints still reference it. There
  is no cascade and no referential check; the forecast just drops it and may emit warnings
  (e.g. a transfer into it, see #7).
- **Why unclear:** Intended convenience, or a data-consistency gap? What should happen to
  bookings on an archived account?
- **Options:** (a) allow and warn (current); (b) block archive while referenced; (c) cascade-
  archive dependents.

### 11. Backup status still carries German text (`last_error`, `last_reason`)
- **Clauses:** `API-BKP` (out-of-scope note), `BKP-018`, `FE-BACKUP-003`.
- **Observed:** Unlike the rest of the API (which emits language-neutral `{code, params}`),
  the backup status fields `last_error` and `last_reason` are German strings produced in the
  backend and shown verbatim by the frontend (e.g. the `.nas-marker` message, `"manuell"`,
  `"zeitplan"`).
- **Why unclear:** This contradicts the "no German in `app/*.py`, frontend owns text" target
  (B-005). Was backup intentionally left out of that refactor?
- **Guidance for tests:** match stable substrings (e.g. `.nas-marker`) or the `last_result`
  enum (`ok`/`unchanged`/`error`), **not** full German sentences.

### 12. Backup scheduler: startup catch-up and hourly-retry conditions
- **Clauses:** `BKP-001`, `BKP-019`.
- **Observed:** The scheduler runs a scheduled backup when `now >= BACKUP_TIME` and no
  scheduled run has happened since today's due time — so starting the app after `BACKUP_TIME`
  triggers an immediate "scheduled" backup. The error-retry branch fires when the last result
  was `error` and the last attempt was >1h ago.
- **Why unclear:** Is the startup catch-up intended (a backup immediately on every restart
  after 03:00)? These timing paths are also untestable in a black-box setting (ENVIRONMENT
  gaps #1–#3).
- **Options:** confirm the catch-up behavior; add a seam so the schedule decision is testable.

### 13. No automated restore and no built-in post-restore verification
- **Clauses:** `RESTORE-001`..`RESTORE-007`.
- **Observed:** Restore is a manual, documented file-copy procedure; the app offers no restore
  endpoint and no "verify this backup is restorable" check beyond `integrity_check` at backup
  time.
- **Why noted:** The task asks for a restore acceptance contract so a test can verify
  restorability. That test must be built around the manual steps (there is no API to exercise).
- **Options:** keep manual (document + external test), or add a verified restore path later.

### 14. Frontend has no stable test hooks (`data-testid`)
- **Clauses:** `FE-CORE-...`, `FE-FORM`, all `FE-*` and `[BROWSER-REQUIRED]` E2E clauses.
- **Observed:** The UI exposes only a few stable ids (`#main`, `#nav`, `#backupPill`,
  `#toast`, `#chart`, `#ftable`, `#fdetail`, `#warn`), `data-view` on nav buttons, and
  `data-name` on form fields. Everything else must be selected by visible German text, ARIA
  roles, or CSS classes, which are presentation-coupled and can drift.
- **Why noted:** Browser tests (Playwright) will be brittle without dedicated hooks.
- **Options:** add `data-testid` attributes to key controls/rows, or accept text/role-based
  selectors (the contracts specify exact visible text to make this workable).
