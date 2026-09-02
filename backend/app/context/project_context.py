from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.context.context_schema import (
    CONTEXT_FIELDS,
    ContextFieldMetadata,
    ContextSource,
    ProjectContextValues,
    StoredProjectContext,
)
from app.models.enums import ProjectDifficulty


class InvalidProjectContextError(ValueError):
    """持久化的 ProjectContext 不符合当前 schema。"""


@dataclass(frozen=True, slots=True)
class ProjectContextSeed:
    project_name: str
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    difficulty: ProjectDifficulty
    requirements: list[dict[str, Any]] | None
    output_requirement: str | None


class ProjectContext:
    def __init__(self, document: StoredProjectContext) -> None:
        self.document = document

    @property
    def version(self) -> int:
        return self.document.version

    @property
    def values(self) -> ProjectContextValues:
        return self.document.values

    @classmethod
    def from_storage(cls, value: object) -> "ProjectContext":
        try:
            return cls(StoredProjectContext.model_validate(value))
        except ValidationError as exc:
            raise InvalidProjectContextError from exc

    def to_storage(self) -> dict[str, Any]:
        return self.document.model_dump(mode="json")


class ContextBuilder:
    def build(
        self,
        seed: ProjectContextSeed,
        *,
        source: ContextSource,
        now: datetime | None = None,
    ) -> ProjectContext:
        updated_at = now or datetime.now(UTC)
        values = ProjectContextValues(
            project_name=seed.project_name,
            language=seed.language,
            framework=seed.framework,
            frontend=seed.frontend,
            backend=seed.backend,
            database=seed.database,
            difficulty=seed.difficulty,
            requirements=seed.requirements,
            output_requirement=seed.output_requirement,
            architecture=None,
            features=[],
            constraints=[],
            extensions={},
        )
        metadata = {
            field_name: ContextFieldMetadata(
                version=1,
                updated_at=updated_at,
                source=source,
            )
            for field_name in CONTEXT_FIELDS
        }
        return ProjectContext(
            StoredProjectContext(
                version=1,
                values=values,
                field_metadata=metadata,
                updated_at=updated_at,
                source=source,
            )
        )
