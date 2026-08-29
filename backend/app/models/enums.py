from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class ProjectDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ProjectStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CourseStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class LearningPlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RecordType(StrEnum):
    STUDY = "study"
    PROJECT = "project"
    WORKFLOW = "workflow"
    AI = "ai"
    COURSE = "course"
    TASK = "task"


class ReportStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


class WorkflowNodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STALE = "stale"


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIRequestStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def enum_type(
    enum_class: type[StrEnum], *, name: str, length: int = 32
) -> SAEnum:
    return SAEnum(
        enum_class,
        values_callable=lambda items: [item.value for item in items],
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=length,
    )

