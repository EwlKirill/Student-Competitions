# Feature Specification: Public Deployment & CI/CD (Milestone 2)

**Feature Branch**: `002-public-deploy-cicd`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "create specification for milestone 2 from technical-requirements.md. Use product-requirements.md as a requirements document. Take into account that the feature 001-hello-world page (milestone 1) is already implemented and tested."

## Overview

Milestone 2 of the walking skeleton for the Student Competitions application. Milestone 1 made
the application runnable and testable on a developer's machine; this milestone takes that exact
same application and puts it on the public internet, with an automated pipeline that keeps it
there.

Three things become true when this milestone is done:

1. Anyone with the address can open the application's home page from any internet-connected
   browser — no developer machine involved.
2. Every proposed change is automatically checked (tests and code style) before it can be
   merged, so broken code cannot reach the shared branch.
3. Every accepted change reaches the public address automatically, with no manual deployment
   steps.

This milestone adds **no** new user-facing behaviour. The page a visitor sees is the milestone 1
home page, unchanged. Its value is that the team gains a production environment, a safety net
and a release mechanism — the three things every later milestone (database, authentication,
roles, competitions) will be delivered through.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anyone can open the application on the public internet (Priority: P1)

A person who is not a developer, on a device that has never seen the project, opens the
application's public address in a browser and is shown the home page — the same page milestone 1
serves locally. No installation, no credentials, no VPN.

**Why this priority**: This is the milestone's headline result and the one thing a stakeholder
can see for themselves. Every other story in this milestone exists to create or protect it.

**Independent Test**: From a device outside the development environment (for example a phone on
mobile data), open the published address and confirm the home page renders.

**Acceptance Scenarios**:

1. **Given** the application has been published, **When** a visitor opens its public address
   from any internet-connected device, **Then** the home page is returned successfully, over a
   secure (encrypted) connection, showing the application name and description.
2. **Given** the application has been published, **When** a visitor opens a path that does not
   exist on the public address, **Then** the friendly "not found" page is shown rather than a
   hosting-platform error or an unhandled failure.
3. **Given** the application has been published, **When** the hosting environment restarts the
   application, **Then** the public address serves the home page again without anyone
   intervening manually.
4. **Given** the application has been published, **When** an automated check requests the public
   address, **Then** it can confirm the service is alive and which version of the application is
   running.

---

### User Story 2 - A proposed change is checked automatically before it can be merged (Priority: P2)

A contributor opens a pull request. Without anyone asking, the project's checks run against the
proposed change — the full test suite plus code style and formatting — and the result is
reported on the pull request. A pull request whose checks fail cannot be merged.

**Why this priority**: The public address is only safe to auto-update if every change has been
verified first. This is the gate that makes story 3 acceptable; it delivers value on its own
even before automatic deployment exists.

**Independent Test**: Open a pull request containing a deliberately failing test, confirm the
checks report failure and merging is blocked; fix the test, confirm the checks turn green and
merging becomes possible.

**Acceptance Scenarios**:

1. **Given** a pull request targeting the shared main branch, **When** it is opened or updated
   with new commits, **Then** the test suite and the code style/formatting checks run
   automatically and their outcome is visible on the pull request.
2. **Given** a pull request whose tests fail, **When** the checks finish, **Then** the pull
   request is reported as failing and is not mergeable.
3. **Given** a pull request whose code violates the project's style or formatting rules,
   **When** the checks finish, **Then** the pull request is reported as failing and is not
   mergeable.
4. **Given** a pull request that passes all checks, **When** the checks finish, **Then** the
   pull request is reported as passing and can be merged.
5. **Given** a failing check, **When** a contributor inspects the result, **Then** the output
   identifies which test or which file and rule failed, without needing to reproduce it locally.

---

### User Story 3 - An accepted change reaches the public address automatically (Priority: P3)

A pull request is merged into the shared main branch. Without any further human action, the new
version is built, verified and published, and within minutes the public address is serving it.

**Why this priority**: It turns the deployment from a one-off manual event into a repeatable
mechanism. It comes after story 2 because deploying automatically is only responsible once
changes are checked automatically.

**Independent Test**: Make a visible, trivial change (for example the page's description text),
merge it to the shared branch, and confirm the public address shows the change without anyone
running a deployment command.

**Acceptance Scenarios**:

1. **Given** a change merged into the shared main branch, **When** the merge completes, **Then**
   the publish process starts automatically with no manual command or console action.
2. **Given** an automatic publish has started, **When** it completes successfully, **Then** the
   public address serves the new version, and the publish outcome is visible to the team.
3. **Given** an automatic publish that fails at any stage, **When** the failure occurs, **Then**
   the previously published version keeps serving visitors and the failure is reported.
4. **Given** a change pushed to any branch other than the shared main branch, **When** the push
   completes, **Then** nothing is published to the public address.
5. **Given** a merge to the shared main branch whose tests fail, **When** the pipeline runs,
   **Then** the new version is not published.

---

### User Story 4 - The application runs the same way everywhere (Priority: P4)

A developer can start the application from a self-contained package, on their own machine, with
one documented command, and get the same behaviour the public address shows — with all
environment-specific values (such as which address and port to listen on) supplied from outside
rather than fixed in the code.

**Why this priority**: It is what makes "works on my machine" and "works in production" the same
statement, and it is how the hosting platform runs the application. It is listed last because it
is a supporting property rather than a visible outcome, but stories 1 and 3 depend on it.

**Independent Test**: On a machine with only the packaging tool installed, build and start the
package from a clean checkout and confirm the home page is served locally from it.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** a developer follows the documented package build and run
   steps, **Then** the application starts and serves the home page locally.
2. **Given** the packaged application, **When** it is started with a different listening port
   supplied from the environment, **Then** it listens on that port without any code change.
3. **Given** the packaged application, **When** it is started with no optional configuration
   supplied, **Then** it starts successfully using documented defaults.
4. **Given** a clean checkout, **When** a developer reads the README, **Then** the package build
   and run commands, the public address, and every environment value the application reads are
   documented there.

---

### Edge Cases

- **Publish fails mid-way** (build error, platform outage, failed start): the previously
  published version continues to serve visitors; the public address never returns a broken or
  half-updated application.
- **Merged change breaks the tests** (for example two independently green pull requests that
  conflict once combined): the pipeline fails on the shared branch and nothing is published.
- **Two merges in quick succession**: the published result matches the later of the two commits;
  an older publish must not overwrite a newer one.
- **Pull request from an outside fork**: verification checks still run; deployment credentials
  are never exposed to code from an untrusted fork.
- **The hosting platform idles or cold-starts the application**: the first request after an idle
  period may be slow but still succeeds and returns the home page.
- **Deployment credentials are missing, expired or wrong**: the publish fails loudly and is
  reported, rather than silently appearing to succeed.
- **A visitor arrives over an insecure connection**: they are moved to the secure connection
  rather than served over an unencrypted one.
- **Checks time out or hang**: the run ends with a reported failure within a bounded time
  instead of blocking the pull request indefinitely.
- **Style-only change**: a change touching only documentation or formatting still passes through
  the same gate and the same publish path — there is no bypass.

## Requirements *(mandatory)*

### Functional Requirements

#### Public availability

- **FR-001**: The application MUST be reachable at a stable public address on the internet that
  anyone can open in a browser without credentials.
- **FR-002**: The public address MUST serve the home page delivered in milestone 1, with
  unchanged content and styling.
- **FR-003**: The public address MUST be served over an encrypted connection, and requests made
  over an unencrypted connection MUST be redirected to the encrypted one.
- **FR-004**: Requests to non-existent paths on the public address MUST return the application's
  own friendly "not found" page.
- **FR-005**: The application MUST expose an address that reports whether the service is alive
  and which version of the application is currently running, suitable for automated monitoring
  and for confirming that a deployment took effect.
- **FR-006**: The application MUST restart and resume serving automatically after a crash or a
  platform-initiated restart, without manual intervention.
- **FR-007**: The public address MUST be recorded in the project's README.

#### Packaging & configuration

- **FR-008**: The application MUST be packaged as a single self-contained, reproducible unit
  that contains everything needed to run it, built from the repository with a documented command.
- **FR-009**: The packaged application MUST be configurable entirely through environment values
  supplied at start time; no environment-specific value (address, port, or later credentials)
  may be hard-coded or committed.
- **FR-010**: The packaged application MUST listen on the network address and port supplied by
  its environment, and MUST start with documented defaults when optional values are absent.
- **FR-011**: The packaged application MUST run identically on a developer machine and on the
  hosting platform; the same package is what gets published.
- **FR-012**: Every environment value the application reads MUST be documented in the README,
  with its purpose and default.

#### Verification of proposed changes

- **FR-013**: Every pull request targeting the shared main branch MUST automatically run the
  full automated test suite.
- **FR-014**: Every pull request targeting the shared main branch MUST automatically run the
  project's code style and formatting checks.
- **FR-015**: Verification MUST run again automatically whenever new commits are added to an
  open pull request.
- **FR-016**: The outcome of verification MUST be reported on the pull request, and a failing
  outcome MUST prevent the pull request from being merged.
- **FR-017**: Failure output MUST identify the failing test, or the file and rule violated,
  clearly enough to act on without reproducing the failure locally.
- **FR-018**: Verification MUST use the exact dependency versions the repository pins, so a
  result is reproducible.
- **FR-019**: Verification MUST complete or fail within a bounded time rather than hanging
  indefinitely.

#### Automatic publishing

- **FR-020**: Merging or pushing to the shared main branch MUST automatically start the publish
  process, with no manual command, console click or local build.
- **FR-021**: Publishing MUST only proceed if the automated tests and style checks pass for the
  commit being published.
- **FR-022**: Pushes to branches other than the shared main branch MUST NOT publish anything to
  the public address.
- **FR-023**: If publishing fails at any stage, the previously published version MUST continue
  serving visitors, and the failure MUST be reported to the team.
- **FR-024**: When several changes are published in quick succession, the public address MUST
  end up serving the newest commit; an earlier publish MUST NOT overwrite a later one.
- **FR-025**: The team MUST be able to see, for the currently published version, which commit it
  was built from and when it was published.
- **FR-026**: The team MUST be able to return the public address to the previously published
  version through a documented procedure.

#### Security of the pipeline

- **FR-027**: All deployment credentials and other secrets MUST be stored in the hosting and
  pipeline platforms' secret storage, and MUST NOT appear in the repository, in the packaged
  application, or in pipeline logs.
- **FR-028**: Verification of changes proposed from outside forks MUST NOT expose deployment
  credentials to those changes.
- **FR-029**: Users MUST NOT be shown internal error details or stack traces on the public
  address.

#### Scope guard

- **FR-030**: This milestone MUST NOT introduce a database, user accounts, roles, competitions,
  questions or any external service integration; the published application MUST start and serve
  the home page with no data store and no third-party credentials.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person outside the development environment can open the public address in a
  browser and see the home page, verified from at least one device and network that has never
  run the project.
- **SC-002**: The home page loads from the public address in under 3 seconds for a request made
  while the application is warm.
- **SC-003**: Over a continuous 24-hour period after publishing, at least 99% of requests to the
  public address return the home page successfully.
- **SC-004**: A pull request containing a deliberately failing test is reported as failing and
  cannot be merged — verified once before the milestone is accepted.
- **SC-005**: A pull request containing a deliberate style or formatting violation is reported as
  failing and cannot be merged — verified once before the milestone is accepted.
- **SC-006**: Automated verification of a pull request completes within 5 minutes of the pull
  request being opened or updated.
- **SC-007**: A change merged to the shared main branch is visible at the public address within
  15 minutes, with zero manual steps performed by anyone — verified once end to end.
- **SC-008**: A deliberately broken publish leaves the public address still serving the previous
  version, with no visitor-facing downtime — verified once before the milestone is accepted.
- **SC-009**: The repository contains zero secrets or credentials, verified by review of the full
  diff for this milestone.
- **SC-010**: A developer with a clean checkout can build and start the packaged application
  locally in under 15 minutes using only the documented commands.
- **SC-011**: Restarting the application on the hosting platform restores service at the public
  address without any human action.

## Assumptions

- **Milestone 1 is the payload.** The published application is exactly the milestone 1 home page;
  no page content, styling or route changes are part of this milestone beyond the
  service-status address in FR-005.
- **Hosting platform**: the constitution names Render as the default, with Railway and Fly.io as
  approved alternatives; the actual choice — and the platform's free/paid tier — is a technical
  decision recorded in this milestone's `plan.md`, not in this spec.
- **Address**: the address provided by the hosting platform is sufficient. A custom domain is out
  of scope; if one is added later it does not change any requirement here.
- **Shared main branch**: the repository's `main` branch is the single integration and release
  branch, as the constitution requires. There is no separate staging environment in this
  milestone — publishing goes straight from `main` to the one public environment.
- **Idle behaviour**: if the chosen hosting tier idles the application when unused, a slow first
  request after idling is acceptable at this milestone and does not count against SC-002, which
  measures a warm request.
- **Merge protection** is enforced by the code-hosting platform's branch settings; configuring
  those settings is part of this milestone's delivery even though it is not a code change.
- **Notification of failures** reaches the team through the code-hosting platform's existing
  notifications; no separate alerting or on-call system is set up.
- **Audience**: the public address is still primarily for the team and reviewers. No students or
  teachers use it yet, so there is no availability commitment beyond SC-003 and no data to
  protect.
- **Rollback** may be performed using the hosting platform's own facility (re-publishing a
  previous version); a bespoke rollback mechanism is not required, only a documented procedure.

## Dependencies

- Milestone 1 (`specs/001-hello-world-page/`) is merged, and its home page and test suite pass —
  already satisfied.
- An account on the chosen hosting platform, with permission to create a service and store
  secrets.
- Administrative permission on the code repository to configure automated checks, required
  status checks on `main`, and repository secrets.

## Out of Scope

- Any new page, route or user-facing feature beyond the milestone 1 home page and the
  service-status address
- Databases, persistence, migrations and data models (milestone 3)
- User accounts, login, sessions, roles and permissions (milestones 4–5)
- Competitions, questions, answers and LLM evaluation (milestones 6–11)
- Custom domains, staging or preview environments, multi-region hosting, autoscaling and
  load testing
- End-to-end browser tests, uptime dashboards, log aggregation and external alerting
  (milestone 12)
- Performance tuning and capacity planning beyond the targets in Success Criteria
