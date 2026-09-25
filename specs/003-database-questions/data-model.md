# Data Model: Database & First Entity — Questions (Milestone 3)

**Feature**: `003-database-questions` | **Date**: 2026-09-24 | **Plan**: [plan.md](./plan.md)

This is the first milestone with persistent data. It defines two tables owned by the application
(`questions`, `boot_counter`), one table owned by Alembic (`alembic_version`), the schemas that
guard writes and shape reads, and the configuration that decides where all of it lives.

Engine rules that apply to everything below: the same models and the same migrations run on
SQLite (local, tests) and PostgreSQL 17 (production, CI). Every timestamp is timezone-aware UTC on
both engines ([research D8](./research.md#d8--timestamps-one-utc-aware-column-type-for-both-engines)).
Constraint names follow one naming convention so they are identical on both engines
([research D14](./research.md#d14--migration-housekeeping-naming-a-single-head-and-drift-detection)).

---

## 1. `Question` — table `questions`

A short knowledge prompt plus the teacher's reference answer (spec *Key Entities*). SQLModel
table model in `app/models/question.py`.

| Field | Python type | Column | Null | Default / source | Notes |
|---|---|---|---|---|---|
| `id` | `int \| None` | `INTEGER`, primary key, autoincrement | no | assigned by the database | Unique identifier (FR-012). `None` only before the first flush. |
| `text` | `str` | `VARCHAR(1000)` | no | from `QuestionCreate` / `QuestionUpdate` | Question text, stored trimmed; internal line breaks preserved (FR-017). |
| `reference_answer` | `str` | `VARCHAR(5000)` | no | from `QuestionCreate` / `QuestionUpdate` | The teacher's correct answer. **Never rendered on a public page** (FR-022). |
| `created_at` | `datetime` (aware, UTC) | `UTCDateTime` → `TIMESTAMP WITH TIME ZONE` (PostgreSQL) / text (SQLite) | no | `utc_now()` at creation | Never changes after creation. |
| `updated_at` | `datetime` (aware, UTC) | `UTCDateTime` | no | `utc_now()` at creation; reset to `utc_now()` by every update | "Last-modified time" (FR-012, US4 scenario 3). |

**Relationships**: none in this milestone. Ownership (milestone 6) and competition links
(milestone 8) are added by later migrations. Deletion is a hard delete, because nothing can yet
refer to a question (spec *Assumptions*). Principle VII's protection of historical results becomes
relevant only when milestone 8 adds the link.

**Default ordering** (FR-016): `ORDER BY created_at ASC, id ASC`. No index is added for it: the
table holds tens to hundreds of rows, and SC-005's 500-question case is a sub-millisecond sort.

### Validation rules (enforced by the schemas in §3, before any database access)

| Rule | `text` | `reference_answer` | Requirement |
|---|---|---|---|
| Required on create | yes | yes | FR-014 |
| Surrounding whitespace | stripped before every other check and before storing | same | FR-014 |
| Non-blank after stripping | yes | yes | FR-014 |
| Maximum length (Unicode code points, after stripping) | 1,000 | 5,000 | FR-014, spec *Assumptions* |
| Internal content | stored exactly: line breaks, Cyrillic, `<`, `&` untouched | same | FR-017, FR-024 |

Violations raise `pydantic.ValidationError`; nothing is written (FR-014). PostgreSQL additionally
enforces the `VARCHAR` lengths as a backstop; SQLite does not, which is why the schema is the
gate.

### Lifecycle

```text
          create_question(QuestionCreate)
(none) ───────────────────────────────────▶ stored
                                            │  ▲
          update_question(id, QuestionUpdate)│  │ updated_at := utc_now()
                                            └──┘
                                            │
          delete_question(id)               ▼
                                          (gone) — get/update/delete now raise QuestionNotFound
```

There are no states beyond "stored" and "gone"; no draft, archive or soft-delete flag (YAGNI).

---

## 2. `BootCounter` — table `boot_counter`

Makes persistence observable: how many times the application has started against this database
(FR-027). SQLModel table model in `app/models/boot_counter.py`.

| Field | Python type | Column | Null | Notes |
|---|---|---|---|---|
| `id` | `int` | `INTEGER`, primary key, `CHECK (id = 1)` | no | Always `1`. The check makes a second row impossible. |
| `boots` | `int` | `BIGINT` | no | Starts at `0` (inserted by the first migration). Only ever incremented. |

**Write path**: exactly one statement, once per application start, in `lifespan`:
`UPDATE boot_counter SET boots = boots + 1 WHERE id = 1`. If the update does not touch exactly one
row, startup fails. The increment is atomic on both engines, so concurrent starts never lose an
increment (FR-028) ([research D7](./research.md#d7--boot-counter-one-row-one-atomic-update-per-start)).

**Read path**: the home page reads `boots` on every request and never writes it (FR-028, US2
scenario 4).

**State transitions**: `0 → 1 → 2 → …`, strictly increasing by one per start. There is no reset
operation.

---

## 3. Schemas — `app/schemas/question.py`

Non-table SQLModel (Pydantic) models. They are the validation boundary for writes and the shape of
public reads ([research D9](./research.md#d9--question-operations-schemas-at-the-boundary-functions-in-a-service)).

| Schema | Fields | Rules |
|---|---|---|
| `QuestionCreate` | `text: str`, `reference_answer: str` | Both required; §1 validation rules. |
| `QuestionUpdate` | `text: str \| None = None`, `reference_answer: str \| None = None` | Each given field follows §1's rules; **at least one** field must be given; a field left out keeps its stored value. |
| `QuestionPublic` | `id: int`, `text: str` | Read-only view for public pages. Has **no** `reference_answer` field, so a template cannot display one (FR-022). |

---

## 4. `DatabaseStatus` — the status-line view

A frozen dataclass returned by `app/services/database_status.py::read_database_status(session)`.
It is not stored; it is assembled per request from three reads.

| Field | Source | Example | Rendered as |
|---|---|---|---|
| `engine` | `session.bind.dialect.name` | `"postgresql"` | `data-engine="postgresql"`; display name "PostgreSQL" (or "SQLite") |
| `revision` | `alembic_version.version_num`, read through Alembic's `MigrationContext.get_current_revision()` | `"3f2a9c1b7d4e"` | `data-revision="…"` and the visible identifier |
| `boots` | `boot_counter.boots` | `14` | `data-boots="14"` and "boot #14" |

The exact markup is fixed in [contracts/http-routes.md](./contracts/http-routes.md).

---

## 5. `alembic_version` — owned by Alembic

One row, one column (`version_num`), maintained by Alembic itself. The application **reads** it
(status line, startup guard) and never writes it (spec *Key Entities*: "Data-structure version").

### Schema versions introduced by this milestone

| Order | Revision (slug) | Kind | Effect |
|---|---|---|---|
| 1 | `create_questions_and_boot_counter` | schema | Creates `questions` and `boot_counter`; inserts the single `boot_counter` row `(1, 0)`. |
| 2 | `seed_sample_questions` | data | Inserts `SAMPLE_QUESTIONS` into `questions` against a frozen `sa.table` definition ([research D6](./research.md#d6--sample-questions-a-data-migration-not-startup-code)). |

Revision ids are Alembic's random 12-character hex ids, assigned when the files are generated. The
head revision is what the status line shows and what the deploy job expects to see.

```text
(empty database) ── rev 1 ──▶ tables exist, boots = 0 ── rev 2 ──▶ sample questions present  = head
```

Applying `upgrade head` to a database already at head changes nothing (FR-008). On PostgreSQL, the
whole upgrade is one transaction behind an advisory lock, so a failure leaves the previous
revision in place and concurrent starts serialise
([research D5](./research.md#d5--migration-atomicity-and-concurrent-starts)).

---

## 6. Sample questions (content of revision 2)

At least 5 are required (FR-019). Six are proposed. One is in Ukrainian and spans two lines, so
production visibly proves non-Latin text and line breaks end to end (spec edge cases). Only the
question text is ever shown publicly. The team may edit the wording before the revision is
generated; after it is applied anywhere, the content is frozen (edit it through a new migration or,
from milestone 6, the question bank).

| # | `text` | `reference_answer` |
|---|---|---|
| 1 | What is the boiling point of water at sea level, in degrees Celsius? | 100 °C (212 °F) at standard atmospheric pressure. |
| 2 | Name the largest planet in the Solar System. | Jupiter. |
| 3 | Who wrote the novel "Nineteen Eighty-Four"? | George Orwell (the pen name of Eric Arthur Blair); it was published in 1949. |
| 4 | Explain in one or two sentences why the daytime sky appears blue. | Sunlight is scattered by air molecules (Rayleigh scattering), and shorter blue wavelengths are scattered far more strongly than longer red ones, so blue light reaches the eye from every direction of the sky. |
| 5 | What is the chemical formula of water, and what does it describe? | H₂O: each molecule consists of two hydrogen atoms bonded to one oxygen atom. |
| 6 | Яка найдовша річка, що протікає територією України?⏎Назвіть її та приблизну довжину в межах країни. | Дніпро — близько 981 км у межах України (загальна довжина — 2 201 км). |

(`⏎` marks a line break inside the stored text.)

All six are inserted in one `bulk_insert` with the same `created_at`, so their public order is
their `id` order, which is the order of this table.

---

## 7. Configuration read from the environment

Extends [milestone 2's configuration](../002-public-deploy-cicd/data-model.md#1-configuration-read-from-the-environment).
The full contract, including error messages, is in
[contracts/configuration.md](./contracts/configuration.md).

| Variable | Read by | Default | Set where | Secret |
|---|---|---|---|---|
| `DATABASE_URL` | `app/core/config.py::resolve_database_url`, called by app startup and by `migrations/env.py` | SQLite at `<project root>/data/student_competitions.sqlite3`, **only when not on Render** | Render dashboard (Neon's direct connection string); CI `image` job (disposable PostgreSQL) | **yes** in production |
| `RENDER` | same function (guard only) | unset | Render, automatically (`true`) | no |
| `TEST_POSTGRES_URL` | `tests/conftest.py` only; never the application | unset → PostgreSQL test cases skipped locally; **required when `CI=true`** | CI `quality` job; a developer's shell | no (disposable, password-less server) |
| `PORT`, `HOST`, `APP_COMMIT`, `RENDER_GIT_COMMIT` | unchanged from milestone 2 | unchanged | unchanged | no |

**Resolution** (first match wins):

```text
DATABASE_URL non-empty ──▶ validate scheme, normalise postgres:// | postgresql:// → postgresql+psycopg://
        │ no
        ▼
RENDER set ──▶ DatabaseConfigError  (startup and `alembic upgrade` both exit non-zero; FR-004)
        │ no
        ▼
sqlite:///<project root>/data/student_competitions.sqlite3   (directory created on demand; FR-002)
```

---

## 8. Validation → requirement traceability

| Requirement | Enforced by |
|---|---|
| FR-001, FR-002, FR-003, FR-004 | §7 resolution; Render/Neon configuration ([quickstart](./quickstart.md) N1–N2) |
| FR-005 | One set of models and migrations; every database test runs on both engines |
| FR-006 | `UTCDateTime` on every timestamp (§1) |
| FR-007, FR-008 | §5; drift and single-head tests ([research D14](./research.md#d14--migration-housekeeping-naming-a-single-head-and-drift-detection)) |
| FR-010 | §5 single-transaction upgrade on PostgreSQL |
| FR-012 … FR-017 | §1, §3 |
| FR-019, FR-020 | §5 revision 2, §6 |
| FR-022 | `QuestionPublic` (§3) |
| FR-025 | `DatabaseStatus` (§4) |
| FR-027, FR-028 | §2 |
