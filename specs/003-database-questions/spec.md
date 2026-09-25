# Feature Specification: Database & First Entity — Questions (Milestone 3)

**Feature Branch**: `003-database-questions`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "using product-requirements.md and technical-requirements.md create specification for the milestone 3. Take into account that molestones 1 and 2 are already implemented."

## Overview

Milestone 3 of the walking skeleton for the Student Competitions application. Milestone 1 made
the application run locally; milestone 2 put it on the public internet behind an automated
check-and-publish pipeline. Until now the application remembers nothing: every restart starts
from zero.

This milestone gives the application a memory, and puts the first real piece of the product in
it — the **question**, the building block of every competition (a short text prompt plus the
teacher's reference answer, per the product requirements).

Four things become true when this milestone is done:

1. The application stores data in a database that survives restarts and redeploys — a local one
   on a developer's machine, a managed one in production — and the structure of that data evolves
   only through versioned, automatically applied changes (migrations).
2. The application has a tested way to create, read, update and delete questions internally.
   There is still **no way to change data through the website**, because nobody can log in yet
   (milestone 4); the operations exist for the milestones that follow.
3. The public home page shows a read-only list of sample questions that are present from the
   first start, so a visitor can see real data coming out of the database.
4. The home page shows a one-line database status — which kind of database is in use, which
   version of the data structure is applied, and how many times the application has started
   against this database. Watching that start count go up across a redeploy is the proof, visible
   to anyone, that production data persists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visitors see sample questions coming from the database (Priority: P1)

A visitor opens the public home page and, below the existing introduction, sees a list of sample
questions — the kind of short, 1–3 line knowledge questions students will later answer in
competitions. The list is read-only: there are no buttons to add, edit or delete anything.

**Why this priority**: This is the milestone's visible, demonstrable slice — the first time the
public site shows data that lives in a database rather than text written into a page. It proves
the whole path end to end: data stored → data read → data rendered, in production.

**Independent Test**: On a freshly set-up environment (local or production), open the home page
and confirm the sample questions are listed; confirm the page offers no way to modify them.

**Acceptance Scenarios**:

1. **Given** a freshly prepared database, **When** a visitor opens the home page, **Then** the
   page lists the sample questions, each showing its question text, in a stable order.
2. **Given** the sample questions are listed, **When** a visitor inspects the page, **Then** there
   is no form, button or link that creates, edits or deletes a question, and no reference answer
   is shown.
3. **Given** the database holds no questions at all, **When** a visitor opens the home page,
   **Then** the page renders normally with a clear "no questions yet" message instead of an empty
   or broken section.
4. **Given** the application has been restarted or redeployed several times, **When** a visitor
   opens the home page, **Then** each sample question appears exactly once — never duplicated.
5. **Given** a question whose text contains markup-like characters (for example `<b>` or `&`),
   **When** it is listed, **Then** it is displayed as literal text and does not alter the page.

---

### User Story 2 - Data survives restarts and redeploys, and anyone can see that it does (Priority: P2)

The home page shows a single status line such as "Database: *engine name* · schema
revision *abc123* · boot #14". Each time the application starts against the same database, the boot number
goes up by at least one. A reviewer notes the number, triggers a redeploy, reloads the page and
sees a higher number — proof that the production database kept its data through the redeploy.

**Why this priority**: Persistence is the actual purpose of adding a database; without it, every
later milestone (accounts, competitions, results) would lose data on each release. The status line
makes an otherwise invisible property checkable by anyone in seconds. It ranks below story 1 only
because it verifies the data path story 1 establishes.

**Independent Test**: Read the boot number on the public home page, merge a trivial change (or
restart the service), wait for the new version to be live, reload, and confirm the boot number is
higher and the sample questions are still present.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** a visitor opens the home page, **Then** a status
   line shows the kind of database in use, the identifier of the data-structure version currently
   applied, and the current boot count.
2. **Given** the home page shows boot count *N*, **When** the application is restarted or
   redeployed against the same database, **Then** the home page afterwards shows a boot count
   greater than *N*.
3. **Given** the application is running locally with no database configuration, **When** a
   developer opens the home page, **Then** the status line identifies the local database kind;
   **and given** the production deployment, **Then** it identifies the production database kind.
4. **Given** the boot count is shown, **When** the page is reloaded repeatedly without a restart,
   **Then** the boot count does not change — it counts application starts, not page views.
5. **Given** a new release that includes a data-structure change, **When** it has been published,
   **Then** the status line shows the new data-structure version identifier.

---

### User Story 3 - The data structure evolves safely through versioned migrations (Priority: P3)

A developer changes the shape of stored data (for example, the question entity itself in this
milestone). The change is captured as a versioned migration kept in the repository. Starting the
application locally, running the tests, and publishing to production all bring the database up to
the latest version automatically; nobody runs manual commands against the production database.

**Why this priority**: Every later milestone adds entities (users, sessions, competitions,
answers, results). A reliable, automatic, versioned path for structural changes is what makes
those milestones safe to ship. It is foundational rather than visible, so it ranks after the
stories a stakeholder can see.

**Independent Test**: From an empty database, apply all migrations and confirm the question data
and the sample questions are present; apply them again and confirm nothing changes; publish a
release and confirm production reports the latest data-structure version.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** the migrations are applied, **Then** the database is at
   the latest version, the question store exists and the sample questions are present.
2. **Given** a database already at the latest version, **When** the migrations are applied again,
   **Then** nothing changes and no error occurs.
3. **Given** a release is being published, **When** the publish runs, **Then** pending migrations
   are applied to the production database automatically, before the new version starts serving
   visitors.
4. **Given** a migration fails during a publish, **When** the failure occurs, **Then** the publish
   is reported as failed, the previously published version keeps serving visitors, and the
   production data is not left half-changed.
5. **Given** the same set of migrations, **When** they are applied to the local database engine and
   to the production database engine, **Then** both end up with an equivalent structure and the
   same sample questions.

---

### User Story 4 - Question operations are proven correct on both database engines (Priority: P4)

The application gains an internal set of operations for questions — create, read one, list,
update, delete — that later milestones (the teacher's question bank in milestone 6, competitions
in milestone 8) will build on. They are not exposed through any web page or address yet. Their
behaviour is verified by automated tests that run on every pull request against **both** the
local database engine and the production database engine.

**Why this priority**: It is the foundation for the question bank, and running the same tests on
both engines is what stops "works locally, breaks in production" database bugs. It is a supporting
capability with no visitor-facing outcome in this milestone, so it ranks last.

**Independent Test**: Open a pull request; confirm the question-operation tests run against both
database engines and all pass; introduce a deliberate defect in one operation and confirm the
checks fail and the pull request cannot be merged.

**Acceptance Scenarios**:

1. **Given** valid question text and reference answer, **When** a question is created, **Then** it
   is stored with a unique identifier and can be read back with identical content.
2. **Given** several stored questions, **When** they are listed, **Then** all of them are returned
   in a stable, predictable order.
3. **Given** a stored question, **When** its text or reference answer is updated, **Then** reading
   it back returns the new content and its last-modified time has advanced.
4. **Given** a stored question, **When** it is deleted, **Then** it can no longer be read or listed.
5. **Given** an identifier that matches no question, **When** it is read, updated or deleted,
   **Then** the operation reports "not found" explicitly rather than failing unpredictably or
   silently doing nothing.
6. **Given** empty (or whitespace-only) question text or reference answer, or text over the
   allowed length, **When** a question is created or updated, **Then** the operation is rejected
   with a clear validation error and nothing is stored or changed.
7. **Given** a pull request, **When** the automated checks run, **Then** the question-operation
   tests run against both database engines, and a failure on either engine fails the checks.

---

### Edge Cases

- **Database unreachable at request time** (production database briefly down): the home page
  still renders with a friendly notice in place of the question list and status line; no stack
  trace or internal error detail is shown. The liveness address from milestone 2 keeps reporting
  that the process is running, so the hosting platform does not restart-loop the service because
  of a database blip.
- **Database unreachable at startup**: the application does not report itself as ready and serve
  a half-working release; the publish fails and the previous version keeps serving (milestone 2
  behaviour).
- **Production database configuration missing or wrong**: the deployed application fails loudly
  instead of silently falling back to a local, throw-away database — a silent fallback would lose
  all data on the next redeploy while appearing healthy.
- **Two instances start at the same time** (an overlapping zero-downtime redeploy): both starts are
  counted, the count never goes down or loses an increment, and the sample questions are still not
  duplicated.
- **Migration interrupted mid-way**: the database is left at the previous consistent version, not
  a partial one; retrying the publish completes it.
- **Sample data already present** (every start after the first): nothing is re-inserted or
  overwritten.
- **Many questions stored** (well beyond the samples, for example 500): the home page still loads
  within the success-criteria time, showing the list in its stable order.
- **Long or multi-line question text**: line breaks within the 1–3 line text are preserved or shown
  readably, and long text wraps without breaking the page layout on a phone-width screen.
- **Non-Latin text** (for example Ukrainian): stored and displayed without corruption on both
  database engines.
- **Tests running in parallel or repeatedly**: each test run starts from a known database state and
  leaves nothing behind that affects the next run, the developer's local data, or production.

## Requirements *(mandatory)*

### Functional Requirements

#### Database & persistence

- **FR-001**: The application MUST store its data in a database that persists across application
  restarts and redeploys, in every environment where it runs.
- **FR-002**: Locally, the application MUST work with a file-based local database and MUST start
  with no database configuration supplied, using a documented default location.
- **FR-003**: In production, the application MUST use the managed production database, whose
  connection details are supplied only through the environment and stored in the hosting
  platform's secret storage.
- **FR-004**: The deployed application MUST NOT silently fall back to a local or temporary
  database when production database configuration is missing or invalid; it MUST fail to start and
  report why (without revealing credentials).
- **FR-005**: The same application code and the same migrations MUST work on both the local and
  the production database engine.
- **FR-006**: All stored timestamps MUST be recorded in UTC with an explicit time zone.

#### Migrations

- **FR-007**: Every change to the structure of stored data MUST be expressed as a versioned
  migration kept in the repository; the application MUST NOT create or alter its structure by any
  other means.
- **FR-008**: Applying migrations MUST bring any database — empty or at an older version — to the
  latest version, and applying them to a database already at the latest version MUST change
  nothing.
- **FR-009**: Pending migrations MUST be applied automatically as part of every production
  publish, before the new version serves visitors, with no manual database commands.
- **FR-010**: A failed migration MUST fail the publish, MUST leave the database at its previous
  consistent version, and MUST leave the previously published version serving visitors.
- **FR-011**: The documented local setup MUST bring a developer's local database to the latest
  version with one documented command (or automatically at start).

#### Question entity & operations

- **FR-012**: The system MUST store questions, each with a unique identifier, question text, a
  reference (correct) answer as text, a creation time and a last-modified time.
- **FR-013**: The system MUST provide internal operations to create a question, read a question by
  identifier, list all questions, update a question's text and/or reference answer, and delete a
  question.
- **FR-014**: Question text and reference answer MUST both be required and non-blank after trimming
  surrounding whitespace, and MUST each respect a maximum length (see Assumptions); invalid input
  MUST be rejected with a clear validation error and MUST NOT change stored data.
- **FR-015**: Reading, updating or deleting a question that does not exist MUST produce an explicit
  "not found" outcome.
- **FR-016**: Listing questions MUST return them in a stable, documented order (oldest first by
  creation time, ties broken by identifier).
- **FR-017**: Question text and reference answers MUST preserve their content exactly as stored,
  including line breaks and non-Latin characters.
- **FR-018**: The application MUST NOT expose any web page, form or address that creates, updates
  or deletes questions (or any other data) in this milestone, because there is no authentication
  yet.

#### Sample questions

- **FR-019**: A fixed set of at least 5 sample questions, each with a reference answer, MUST be
  present in every newly prepared database — local and production — without manual action.
- **FR-020**: Sample questions MUST be inserted only once per database; later starts, redeploys
  and re-applied migrations MUST NOT duplicate or overwrite them.

#### Public home page

- **FR-021**: The home page MUST keep the milestone 1 introduction and additionally list all stored
  questions, read-only, showing each question's text in the order defined by FR-016.
- **FR-022**: The home page MUST NOT display reference answers.
- **FR-023**: When no questions are stored, the home page MUST show an explicit "no questions yet"
  message.
- **FR-024**: Question text MUST be displayed as literal text; markup-like content in a question
  MUST NOT be interpreted by the browser.
- **FR-025**: The home page MUST show a database status line containing: the kind of database in
  use (local vs. production engine, by name), the identifier of the latest applied migration, and
  the boot count.
- **FR-026**: When the database cannot be reached while rendering the home page, the page MUST
  still render, replacing the question list and status line with a friendly "data temporarily
  unavailable" notice and no internal error details.

#### Boot count

- **FR-027**: The application MUST keep, in the database, a count of how many times the application
  has started against that database, incrementing it exactly once per application start.
- **FR-028**: The boot count MUST NOT change on page views or any other request, and MUST never
  decrease or lose an increment, including when two instances start at the same time.

#### Service status & pipeline

- **FR-029**: The milestone 2 liveness address MUST keep working and MUST remain independent of
  database availability, so a temporary database outage does not cause the hosting platform to
  restart the service.
- **FR-030**: The automated checks on every pull request and every release MUST run the
  question-operation and migration tests against both the local and the production database
  engine; a failure on either MUST fail the checks and block the merge or publish.
- **FR-031**: Tests MUST run against isolated, disposable databases and MUST NOT read or modify a
  developer's local data or the production database.
- **FR-032**: Every new environment value the application reads (such as the database location)
  MUST be documented in the README with its purpose and default, and database credentials MUST NOT
  appear in the repository, in the packaged application or in logs.

#### Scope guard

- **FR-033**: This milestone MUST NOT introduce user accounts, login, sessions, roles, competitions,
  answers, evaluation, or any write action available through the website.

### Key Entities *(include if feature involves data)*

- **Question**: A short knowledge prompt (usually 1–3 lines) that will later be used in
  competitions and can be reused across many of them. Attributes: unique identifier, question text,
  reference answer (the teacher-prepared correct answer used later as the input for scoring),
  creation time, last-modified time. In this milestone questions have no owner and no link to any
  other entity; ownership and competition links arrive in milestones 6 and 8.
- **Application boot record**: A single counter kept in the database that records how many times
  the application has started against that database. It exists to make persistence observable; it
  is not user data.
- **Data-structure version**: The identifier of the latest migration applied to the database, as
  tracked by the migration mechanism itself. Displayed on the home page; not edited by the
  application.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the public address, the home page lists all sample questions (at least 5), each
  exactly once — verified from a device outside the development environment.
- **SC-002**: The boot count shown on the public home page is strictly higher after a redeploy than
  before it, with all sample questions still present — verified once end to end before the
  milestone is accepted.
- **SC-003**: The question-operation tests (create, read, list, update, delete, not-found and
  validation cases) pass against both database engines on every pull request — 100% of these tests
  run on both engines.
- **SC-004**: A pull request that introduces a defect in a question operation is reported as
  failing and cannot be merged — verified once before the milestone is accepted.
- **SC-005**: The home page, with the question list and status line, loads in under 3 seconds for a
  warm request on the public address, and in under 3 seconds locally with 500 stored questions.
- **SC-006**: Applying all migrations to an empty database, then applying them a second time,
  results in the latest version with exactly the sample questions and no errors — on both engines.
- **SC-007**: A deliberately failing migration in a publish leaves the public address serving the
  previous version with its data intact — verified once before the milestone is accepted.
- **SC-008**: A developer with a clean checkout can run the application locally and see the sample
  questions and the status line in under 15 minutes, using only the documented commands and no
  database configuration.
- **SC-009**: Automated verification of a pull request, now including both database engines,
  still completes within 10 minutes.
- **SC-010**: The repository, the packaged application and the pipeline logs contain zero database
  credentials — verified by review of the full diff and a publish log for this milestone.

## Assumptions

- **Milestones 1 and 2 are live.** The home page, friendly error page, liveness address, packaged
  application, pull-request checks and automatic publishing from `main` all exist and are reused
  unchanged except where this spec extends them. Milestone 2's scope guard ("no database") is
  deliberately lifted by this milestone.
- **Database engines** are fixed by the constitution: a lightweight file-based engine locally and in
  tests, a managed server engine in production. Which managed production offering (and its tier)
  is used is a technical decision for this milestone's `plan.md`. If the chosen tier has an expiry
  or data-retention limit, that limit and how it is handled are recorded there.
- **No write endpoints.** "CRUD" in this milestone means the internal operations and their tests;
  the teacher-facing question bank with forms arrives in milestone 6, after authentication (4) and
  roles (5).
- **Reference answers are not public.** Reference answers are the basis for scoring and must not be
  exposed to students later, so the public page shows only question text even for samples. Showing
  sample reference answers would set a precedent that later milestones would have to reverse.
- **Sample questions** are general-knowledge examples written by the team and shipped with the
  application; they are illustrative, not a curriculum. They may later be edited or removed by
  teachers once the question bank exists.
- **Length limits**: question text up to 1,000 characters and reference answer up to 5,000
  characters — generous for "usually 1–3 lines" while preventing unbounded input.
- **Deletion is permanent** in this milestone because no competition, answer or result can yet refer
  to a question. Protecting historical competition results from question deletion (constitution
  Principle VII) is addressed in milestone 8 when that link is introduced.
- **Boot count semantics**: "boot" means one application process start against the database. A
  hosting platform that briefly runs an old and a new instance during a redeploy, or restarts an
  idle service, may increase the count by more than one per redeploy; the requirement is only that
  it increases and never decreases.
- **Status line audience**: the status line is a development-stage diagnostic shown publicly while
  the application has no real users; it may be moved or removed in a later milestone (for example
  milestone 12 hardening).
- **Liveness vs. readiness**: the liveness address stays database-independent (it must answer
  within the platform's health-check window). Whether a separate database-aware readiness signal is
  added is a technical decision for `plan.md`, as long as FR-004 and the startup edge case hold.
- **Ordering**: oldest-first is a sensible default for a small read-only list; sorting and paging
  are out of scope.

## Dependencies

- Milestones 1 and 2 (`specs/001-hello-world-page/`, `specs/002-public-deploy-cicd/`) are merged,
  deployed and their acceptance tests pass — already satisfied.
- Access to create a managed production database on (or alongside) the hosting platform and to
  store its connection details as a secret.
- The pull-request checks environment can provide a disposable instance of the production database
  engine for tests.

## Out of Scope

- Any web form, button or address that creates, edits or deletes data (milestones 6+)
- Email login, sessions, users, roles and permissions (milestones 4–5, 7)
- Teacher question bank: bulk upload, editing UI, ownership of questions (milestone 6)
- Competitions, participants, answers, LLM evaluation and results (milestones 8–11)
- Educational institutions and student records (milestone 7)
- Search, filtering, sorting options and pagination of questions
- Database backups, point-in-time restore, replicas and performance tuning beyond the Success
  Criteria
- Downgrading (reversing) migrations in production — only forward migration is required; rollback
  of a failed release relies on migrations being applied atomically (FR-010)
