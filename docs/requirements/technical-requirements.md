# Technical Requirements

## Technology Stack

| Area | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | Server-side rendering: Jinja2 + HTMX + Pico.css |
| Database | SQLite locally, PostgreSQL in production, via SQLModel + Alembic |
| Authentication | Email code (OTP) + server-side sessions in a signed cookie |
| Answer evaluation | LLM API call (Claude or OpenAI) with structured output |
| Infrastructure & deployment | Docker + Render (or Railway / Fly.io) |
| Tooling & tests | uv, ruff, pytest, later Playwright |
| Development process | GitHub Spec Kit |

## Milestones

The ladder follows a "walking skeleton" approach: first ship an empty skeleton to the internet, then grow it with vertical slices. Each step ends with a working, testable and meaningful result.

1. **Hello World locally.** FastAPI serves a single HTML page via Jinja2.
   _Test:_ the application starts, the page opens, there is a first pytest test for the endpoint.

2. **Deploy Hello World to the internet + CI/CD.** Dockerfile, deployment to Render, public URL. GitHub Actions runs tests and linting on PRs, auto-deploy on push to `main`.
   _Test:_ the page is accessible from outside, the pipeline is green.

3. **Database + first entity.** Connect the database (SQLite locally, Postgres in production) with Alembic migrations. Create the "Question" model with a CRUD layer covered by tests (no write endpoints, since there is no authentication yet). The public page shows a read-only list of seeded sample questions and a database status line (database type, migration revision, boot count).
   _Test:_ CRUD tests pass on SQLite and Postgres in CI; in production, the sample questions are visible and the boot count increases across a redeploy.

4. **Email code authentication.** Email input form → code sent to email → code verification → session.
   _Test:_ a user can log in, a protected page is accessible only to logged-in users.

5. **Roles and authorization.** Three roles (student / teacher / administrator); the list of administrators is set via configuration at deploy time. Route protection by role.
   _Test:_ access to pages depends on the role.

6. **Question bank (teacher).** Uploading a list of questions, viewing, editing, reference answers for questions.
   _Test:_ question CRUD works and is visible only to teachers.

7. **User management.** A teacher adds students (email, first name, last name, educational institution, year, group). An administrator manages teachers and students. Profiles for all roles.
   _Test:_ users are created, profiles are edited.

8. **Creating a competition (teacher).** A competition with a start time, duration, assignment to a group/students, a set of questions from the bank and reference answers.
   _Test:_ a competition is created and correctly linked to questions and participants.

9. **Taking a competition (student).** List of assigned competitions, enforcement of the time window and duration, entering and submitting text answers.
   _Test:_ answers are saved; the competition is not accessible outside its time window.

10. **Answer evaluation via LLM.** Each answer receives a score of 1–10 that takes level of detail into account; results are saved to the database.
    _Test:_ evaluation returns a structured result and it is persisted.

11. **Best answer selection + results.** For each question, the best answer is selected from the group's answers; competition results are saved and displayed.
    _Test:_ the best answer is determined, the results page works.

12. **Polish and hardening.** Results dashboards, E2E tests with Playwright, error handling, security. (Optional stretch goal: move part of the UI to React.)
