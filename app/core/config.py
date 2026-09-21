"""User-facing application strings.

Single source of truth for the name, tagline and description that appear on the page, in the
browser tab and in the test assertions. Values are literals, not read from the environment:
the application must start with no configuration at all (FR-010).
"""

APP_NAME = "Student Competitions"

APP_TAGLINE = "Online knowledge competitions for students."

APP_DESCRIPTION = (
    "Student Competitions is a web application for running online knowledge competitions in "
    "schools and universities. Teachers build a question bank and open a competition, students "
    "answer the questions in writing, and every answer is scored automatically."
)
