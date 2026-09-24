# Internal Contract: Question operations (`app/services/questions.py`)

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](../plan.md)

The internal create/read/list/update/delete interface for questions (FR-013). This milestone
exposes it through **no** route (FR-018). It is the interface that milestone 6's question bank
and milestone 8's competitions build on, so its behaviour is fixed here and verified on both
database engines (FR-030, SC-003).

Types are in [data-model.md](../data-model.md): `Question` (§1), `QuestionCreate`,
`QuestionUpdate`, `QuestionPublic` (§3).

---

## Conventions

- Every function takes an open `sqlmodel.Session` as its first argument. The **caller owns the
  session**; functions that write call `session.commit()` themselves and `session.refresh()` the
  returned object, so one call is one committed unit of work.
- Validation happens when the caller builds `QuestionCreate` / `QuestionUpdate`. A
  `pydantic.ValidationError` is raised **before** any service function runs, so invalid input can
  never reach the database (FR-014).
- A missing identifier raises `QuestionNotFound(question_id)`, a subclass of `LookupError`
  defined in `app/services/questions.py`, whose message names the id (FR-015). No function returns
  `None` for "not found".
- Timestamps come from `app.core.db.utc_now()` and are always timezone-aware UTC (FR-006).

---

## Functions

| Function | Returns | Behaviour | Raises |
|---|---|---|---|
| `create_question(session, data: QuestionCreate)` | `Question` | Inserts a row with `created_at = updated_at = utc_now()`; returns it with its new unique `id` (US4 scenario 1) | — |
| `get_question(session, question_id: int)` | `Question` | Returns the stored question exactly as stored (FR-017) | `QuestionNotFound` |
| `list_questions(session)` | `list[Question]` | All questions, `ORDER BY created_at, id` (FR-016); empty list when none | — |
| `update_question(session, question_id: int, data: QuestionUpdate)` | `Question` | Replaces each field present in `data`, leaves the others unchanged, sets `updated_at = utc_now()` (US4 scenario 3) | `QuestionNotFound` (nothing changed) |
| `delete_question(session, question_id: int)` | `None` | Deletes the row permanently; afterwards `get` raises and `list` omits it (US4 scenario 4) | `QuestionNotFound` (nothing changed) |

## Neighbouring service: `app/services/database_status.py`

| Function | Returns | Behaviour | Raises |
|---|---|---|---|
| `record_boot(session)` | `int` (the new count) | `UPDATE boot_counter SET boots = boots + 1 WHERE id = 1`, commit, then read back. Called once per start from `lifespan` (FR-027) | `RuntimeError` if the update did not touch exactly one row; any `SQLAlchemyError` from the database |
| `read_database_status(session)` | `DatabaseStatus` | Reads engine name, current Alembic revision and `boots`. Read-only (FR-025, FR-028) | any `SQLAlchemyError` (the page handler turns it into the unavailable notice) |

---

## Behaviour matrix (each row is a test, run on SQLite and PostgreSQL)

| # | Given | When | Then | Spec |
|---|---|---|---|---|
| 1 | valid text and answer | `create_question` | returns a `Question` with an `id`; `get_question(id)` returns identical `text` and `reference_answer` | US4-1 |
| 2 | two creates | compare ids | ids differ | FR-012 |
| 3 | several questions created in a known order, including two with equal `created_at` | `list_questions` | returned in `created_at, id` order, the same on every call | US4-2, FR-016 |
| 4 | a stored question, clock advanced | `update_question` with new `text` only | `text` changed, `reference_answer` unchanged, `updated_at` > previous, `created_at` unchanged | US4-3 |
| 5 | a stored question | `delete_question` | `get_question` raises `QuestionNotFound`; `list_questions` omits it | US4-4 |
| 6 | an id that matches nothing | `get` / `update` / `delete` | each raises `QuestionNotFound`; row count unchanged | US4-5, FR-015 |
| 7 | text `""`, `"   "`, `"\n\t"`; answer likewise | build `QuestionCreate` / `QuestionUpdate` | `ValidationError`; row count and stored values unchanged | US4-6, FR-014 |
| 8 | text of 1,001 characters after stripping; answer of 5,001 | build the schemas | `ValidationError` | FR-014 |
| 9 | text of exactly 1,000 Cyrillic characters; answer of exactly 5,000 | create, then get | accepted; stored and returned unchanged | FR-014, FR-017 |
| 10 | `"  Line one\nLine two  "` | create, then get | stored as `"Line one\nLine two"` (surrounding whitespace stripped, internal break kept) | FR-014, FR-017 |
| 11 | text `"<b>bold</b> & more"` | create, then get | returned exactly | FR-017 |
| 12 | `QuestionUpdate()` with no fields | build it | `ValidationError` | data-model §3 |
| 13 | any stored question | read `created_at`, `updated_at` | both timezone-aware, `utcoffset() == 0` | FR-006 |
| 14 | a fresh database | `record_boot` ×1, then ×1 again | returns 1, then 2 | FR-027 |
| 15 | a fresh database | `record_boot` from N threads on separate sessions at once | final count is exactly N | FR-028 |
| 16 | a fresh database | `read_database_status` twice with no boot between | identical `boots` | FR-028, US2-4 |
