"""The evidence processing pipeline (plan §13).

    RAW EVIDENCE → VALIDATION → EXTRACTION → NORMALIZATION → STRUCTURING → …

Each step is a small plugin: a name, a label for the UI, which evidence types it applies to,
and a function. Adding support for a new kind of evidence = adding a step to STEPS.
Nothing else in FALCON changes (plan §40: "adding a new evidence type should not require
rewriting the platform").

Steps receive a StepContext and return a short summary that is shown to investigators.
They may READ the original file but must never change it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import Evidence


class StepFailed(Exception):
    """A step found a problem the investigator must look at (shown as the job's error)."""


@dataclass
class StepContext:
    db: Session
    evidence: Evidence
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Step:
    name: str
    label: str
    run: Callable[[StepContext], str]
    # Decides from the evidence (usually its detected content type) whether the step runs.
    # None = every evidence item.
    when: Callable[[Evidence], bool] | None = None

    def applies(self, evidence: Evidence) -> bool:
        return self.when is None or self.when(evidence)


def steps_for(evidence: Evidence) -> list[Step]:
    from app.processing.steps import STEPS  # local import: steps import this module

    return [step for step in STEPS if step.applies(evidence)]


def merge_metadata(evidence: Evidence, section: str, values: dict[str, Any]) -> None:
    """Store results under file_metadata[section]. Reassigning the dict makes SQLAlchemy
    notice the change (it does not watch for edits *inside* a JSON value)."""
    evidence.file_metadata = {**(evidence.file_metadata or {}), section: values}
