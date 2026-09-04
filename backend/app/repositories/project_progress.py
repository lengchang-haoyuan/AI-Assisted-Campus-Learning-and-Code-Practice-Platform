from sqlalchemy import case, func, select
from sqlalchemy.sql.selectable import Subquery

from app.models.enums import TaskStatus
from app.models.learning import DailyTask
from app.models.project import Project


def project_progress_rows() -> Subquery:
    """统计与报告共用的项目进度查询，与工作台任务完成率保持一致。"""
    tasks = (
        select(
            DailyTask.project_id,
            DailyTask.user_id,
            func.count(DailyTask.id).label("total"),
            func.sum(case((DailyTask.status == TaskStatus.COMPLETED, 1), else_=0))
            .label("completed"),
        )
        .where(DailyTask.project_id.is_not(None))
        .group_by(DailyTask.project_id, DailyTask.user_id)
        .subquery()
    )
    total = func.nullif(tasks.c.total, 0)
    scaled = tasks.c.completed * 100
    lower = func.floor(scaled / total)
    remainder = scaled % total
    # MySQL ROUND 的 .5 规则不同于 Python round；用整数余数保留工作台的偶数取整。
    rounded = case(
        (remainder * 2 < total, lower),
        (remainder * 2 > total, lower + 1),
        else_=lower + lower % 2,
    )
    return (
        select(
            Project.id.label("project_id"),
            Project.owner_id,
            case((tasks.c.total.is_(None), Project.progress), else_=rounded).label("progress"),
        )
        .outerjoin(
            tasks,
            (tasks.c.project_id == Project.id) & (tasks.c.user_id == Project.owner_id),
        )
        .subquery()
    )
