"""Every table model, imported here so that importing `app.models` makes `SQLModel.metadata`
complete. Alembic's `env.py` and the drift test rely on that; a new model must be added here."""

from app.models.boot_counter import BootCounter
from app.models.question import Question

__all__ = ["BootCounter", "Question"]
