from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    IdMixin,
    MYSQL_TABLE_OPTIONS,
    TimestampMixin,
    UTCDateTime,
)
from app.models.enums import (
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.ai import AIRequest
    from app.models.project import Project
    from app.models.user import User


class Workflow(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_workflows_project_name"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_workflows_project_status", "project_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkflowStatus] = mapped_column(
        enum_type(WorkflowStatus, name="workflow_status", length=16),
        nullable=False,
        server_default=WorkflowStatus.DRAFT.value,
    )
    version: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("1")
    )

    project: Mapped["Project"] = relationship(back_populates="workflows")
    nodes: Mapped[list["WorkflowNode"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    edges: Mapped[list["WorkflowEdge"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )
    runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", passive_deletes=True
    )


class WorkflowNode(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_nodes"
    __table_args__ = (
        UniqueConstraint("workflow_id", "node_key", name="uq_nodes_workflow_key"),
        UniqueConstraint("id", "workflow_id", name="uq_nodes_id_workflow"),
        CheckConstraint("context_version >= 1", name="context_version_positive"),
        Index("ix_workflow_nodes_workflow_status", "workflow_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    workflow_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position_x: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default=text("0.00")
    )
    position_y: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default=text("0.00")
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[WorkflowNodeStatus] = mapped_column(
        enum_type(WorkflowNodeStatus, name="workflow_node_status", length=16),
        nullable=False,
        server_default=WorkflowNodeStatus.PENDING.value,
    )
    context_version: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("1")
    )

    workflow: Mapped[Workflow] = relationship(back_populates="nodes")


class WorkflowEdge(IdMixin, Base):
    __tablename__ = "workflow_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_node_id", "workflow_id"],
            ["workflow_nodes.id", "workflow_nodes.workflow_id"],
            name="fk_edges_source_node_workflow",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_node_id", "workflow_id"],
            ["workflow_nodes.id", "workflow_nodes.workflow_id"],
            name="fk_edges_target_node_workflow",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workflow_id",
            "source_node_id",
            "target_node_id",
            name="uq_edges_workflow_nodes",
        ),
        CheckConstraint("source_node_id <> target_node_id", name="different_nodes"),
        Index("ix_workflow_edges_target", "workflow_id", "target_node_id"),
        MYSQL_TABLE_OPTIONS,
    )

    workflow_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_node_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    target_node_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    condition_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    workflow: Mapped[Workflow] = relationship(
        back_populates="edges",
        primaryjoin="Workflow.id == foreign(WorkflowEdge.workflow_id)",
        overlaps="nodes",
    )


class WorkflowRun(IdMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_workflow_created", "workflow_id", "created_at"),
        Index("ix_workflow_runs_started_by_status", "started_by_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    workflow_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_by_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[WorkflowRunStatus] = mapped_column(
        enum_type(WorkflowRunStatus, name="workflow_run_status", length=16),
        nullable=False,
        server_default=WorkflowRunStatus.PENDING.value,
    )
    context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    workflow: Mapped[Workflow] = relationship(back_populates="runs")
    started_by: Mapped["User | None"] = relationship(back_populates="workflow_runs")
    ai_requests: Mapped[list["AIRequest"]] = relationship(
        back_populates="workflow_run", passive_deletes=True
    )
