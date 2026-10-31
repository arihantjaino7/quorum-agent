"""Row → wire-type converters (models.py → schemas.py)."""

from app import models, schemas


def decision(row: models.Decision) -> schemas.Decision:
    return schemas.Decision.model_validate(row, from_attributes=True)


def task(row: models.Task) -> schemas.Task:
    return schemas.Task.model_validate(row, from_attributes=True)


def meeting(row: models.Meeting) -> schemas.Meeting:
    return schemas.Meeting.model_validate(row, from_attributes=True)
