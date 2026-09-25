"""Question operations: the internal interface milestones 6 and 8 build on.

See specs/003-database-questions/contracts/question-service.md. No route exposes these functions
in this milestone (FR-018), and they enforce no authorization, because roles do not exist yet — a
recorded Principle IV deviation. Milestone 6, their first real caller, must put a teacher role
check in front of `create_question`, `update_question` and `delete_question` and test it.

Every function takes an open session as its first argument; the caller owns the session. Each
write is one committed unit of work. Input arrives already validated by the schemas.
"""

from sqlmodel import Session, select

from app.core.db import utc_now
from app.models import Question
from app.schemas.question import QuestionCreate, QuestionUpdate


class QuestionNotFound(LookupError):
    """No question has this id (FR-015). Raised instead of returning `None`."""

    def __init__(self, question_id: int) -> None:
        super().__init__(f"Question {question_id} not found")
        self.question_id = question_id


def create_question(session: Session, data: QuestionCreate) -> Question:
    """Store a new question and return it with its new id."""
    now = utc_now()
    question = Question(
        text=data.text, reference_answer=data.reference_answer, created_at=now, updated_at=now
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def get_question(session: Session, question_id: int) -> Question:
    """The stored question, exactly as stored."""
    question = session.get(Question, question_id)
    if question is None:
        raise QuestionNotFound(question_id)
    return question


def list_questions(session: Session) -> list[Question]:
    """All questions, oldest first; ties on creation time broken by id (FR-016)."""
    return list(session.exec(select(Question).order_by(Question.id.desc())))


def update_question(session: Session, question_id: int, data: QuestionUpdate) -> Question:
    """Replace the fields given in `data`, keep the others, and mark the question modified."""
    question = get_question(session, question_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(question, field, value)
    question.updated_at = utc_now()
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def delete_question(session: Session, question_id: int) -> None:
    """Delete the question permanently. Nothing refers to questions yet, so a hard delete is
    safe; milestone 8's competition links will need to revisit this."""
    session.delete(get_question(session, question_id))
    session.commit()
