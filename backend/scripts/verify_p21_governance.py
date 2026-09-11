from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select, update

from app.core.database import get_session_factory
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.community import (
    Comment,
    CommunityGovernanceAction,
    CommunityGovernanceCase,
    CommunityPublication,
    CommunityPublicationVersion,
    Favorite,
    Like,
    ProjectView,
)
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project, Tag, project_tags
from app.models.submission import Notification
from app.models.user import User
from app.repositories.community import CommunityRepository
from app.services.auth import UserIdentity
from app.services.community import CommunityService


def identity(user: User) -> UserIdentity:
    return UserIdentity(id=user.id, username=user.username, email=user.email, avatar_url=None, bio=None, is_active=True, created_at=user.created_at)


def main() -> int:
    marker = uuid4().hex[:10]
    session = get_session_factory()()
    user_ids: list[int] = []
    project_id: int | None = None
    publication_id: int | None = None
    case_ids: list[int] = []
    try:
        now = datetime.now(UTC)
        users = [
            User(username=f"p21_owner_{marker}", email=f"p21_owner_{marker}@example.invalid", password_hash="fixture-not-login"),
            User(username=f"p21_viewer_{marker}", email=f"p21_viewer_{marker}@example.invalid", password_hash="fixture-not-login"),
            User(username=f"p21_admin_{marker}", email=f"p21_admin_{marker}@example.invalid", password_hash="fixture-not-login"),
        ]
        session.add_all(users)
        session.flush()
        user_ids = [user.id for user in users]
        for user, role in zip(users, [CampusRole.STUDENT, CampusRole.STUDENT, CampusRole.ADMINISTRATOR], strict=True):
            session.add(CampusMembership(user_id=user.id, role=role, status=MembershipStatus.ACTIVE, verified_by_user_id=users[2].id, verified_at=now, revision=1))
        project = Project(owner_id=users[0].id, name=f"P21 隔离验收 {marker}", description="V1 私人说明", difficulty=ProjectDifficulty.BEGINNER, status=ProjectStatus.IN_PROGRESS, language="Python", framework="FastAPI", is_published=False, view_count=0)
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id
        owner, viewer, administrator = (identity(user) for user in users)
        service = CommunityService(CommunityRepository(session))

        first = service.request_publication(owner, project_id=project.id, request_key=f"publish_{marker}", expected_project_updated_at=project.updated_at, kind="work", tag_names=[f"P21-{marker}"], attribution=users[0].username, source_license_statement="隔离验收原创内容", ai_assistance_statement="未使用 AI", human_review_statement=None)
        publication_id = int(first["id"])
        replay = service.request_publication(owner, project_id=project.id, request_key=f"publish_{marker}", expected_project_updated_at=project.updated_at, kind="work", tag_names=[f"P21-{marker}"], attribution=users[0].username, source_license_statement="隔离验收原创内容", ai_assistance_statement="未使用 AI", human_review_statement=None)
        if replay["pending_version_number"] != 1:
            raise RuntimeError("重复申请生成了额外版本")
        approved = service.decide_publication(administrator, publication_id=publication_id, expected_revision=int(first["revision"]), decision="approve", reason="隔离验收通过")
        if approved["status"] != "approved":
            raise RuntimeError("发布审核未通过")
        session.expire_all()
        diagnostic = session.execute(
            select(
                Project.is_published,
                CommunityPublication.status,
                CommunityPublication.public_version_number,
                CommunityPublicationVersion.version_number,
            )
            .join(CommunityPublication, CommunityPublication.project_id == Project.id)
            .join(CommunityPublicationVersion, CommunityPublicationVersion.publication_id == CommunityPublication.id)
            .where(Project.id == project.id)
        ).one()
        if diagnostic != (True, "approved", 1, 1):
            raise RuntimeError(f"审核后持久化状态异常：{diagnostic}")
        public_v1 = service.get_project(project.id, viewer)
        if public_v1.description != "V1 私人说明":
            raise RuntimeError("公开快照内容不正确")

        project.description = "V2 私人修改，不应静默公开"
        session.commit()
        session.refresh(project)
        still_v1 = service.get_project(project.id, viewer)
        if still_v1.description != "V1 私人说明":
            raise RuntimeError("私人修改替换了公开快照")

        report = service.report(viewer, request_key=f"report_project_{marker}", target_type="project", target_id=project.id, reason="隔离验收举报")
        replay_report = service.report(viewer, request_key=f"report_project_{marker}", target_type="project", target_id=project.id, reason="隔离验收举报")
        if report["id"] != replay_report["id"]:
            raise RuntimeError("重复举报未保持幂等")
        case_ids.append(int(report["id"]))
        resolved = service.decide_case(administrator, case_id=int(report["id"]), expected_revision=int(report["revision"]), decision="accept", reason="隔离验收下架")
        try:
            service.get_project(project.id, viewer)
            raise RuntimeError("下架内容仍可直接访问")
        except ResourceNotFoundError:
            pass
        target_view = service.case_list(owner, status=None, page=1, page_size=20)["items"]
        target_case = next(item for item in target_view if item["id"] == report["id"])
        if target_case["reason"] is not None or target_case["opened_by_user_id"] is not None:
            raise RuntimeError("举报者信息或理由暴露给内容作者")
        appeal = service.appeal(owner, action_id=int(resolved["resolved_action_id"]), request_key=f"appeal_project_{marker}", reason="隔离验收复核")
        case_ids.append(int(appeal["id"]))
        service.decide_case(administrator, case_id=int(appeal["id"]), expected_revision=int(appeal["revision"]), decision="accept", reason="隔离验收恢复")
        service.get_project(project.id, viewer)

        comment = service.create_comment(project.id, viewer, "P21 隔离验收评论")
        comment_report = service.report(owner, request_key=f"report_comment_{marker}", target_type="comment", target_id=comment.id, reason="隔离验收评论举报")
        case_ids.append(int(comment_report["id"]))
        hidden = service.decide_case(administrator, case_id=int(comment_report["id"]), expected_revision=int(comment_report["revision"]), decision="accept", reason="隔离验收隐藏")
        comments = service.list_comments(project.id, owner, page=1, page_size=20)
        if any(item.id == comment.id for item in comments.items):
            raise RuntimeError("隐藏评论仍出现在公开列表")
        comment_appeal = service.appeal(viewer, action_id=int(hidden["resolved_action_id"]), request_key=f"appeal_comment_{marker}", reason="隔离验收评论复核")
        case_ids.append(int(comment_appeal["id"]))
        service.decide_case(administrator, case_id=int(comment_appeal["id"]), expected_revision=int(comment_appeal["revision"]), decision="accept", reason="隔离验收恢复评论")
        if not any(item.id == comment.id for item in service.list_comments(project.id, owner, page=1, page_size=20).items):
            raise RuntimeError("支持复核后评论未恢复")

        try:
            service.list_projects(UserIdentity(id=999999999, username="outsider", email="outsider@example.invalid", avatar_url=None, bio=None, is_active=True, created_at=now), page=1, page_size=12, tag_slug=None)
            raise RuntimeError("无校园身份用户进入了社区")
        except PermissionDeniedError:
            pass
        notification_count = len(
            list(
                session.scalars(
                    select(Notification).where(Notification.recipient_user_id.in_(user_ids))
                )
            )
        )
        print({"publication": "apply-approved-taken_down-restored", "comment": "visible-hidden-restored", "idempotent": True, "privacy_redaction": True, "campus_boundary": True, "notifications": notification_count})
        return 0
    finally:
        session.rollback()
        if user_ids:
            publication_ids = list(session.scalars(select(CommunityPublication.id).where(CommunityPublication.owner_user_id.in_(user_ids))))
            governance_case_ids = list(session.scalars(select(CommunityGovernanceCase.id).where((CommunityGovernanceCase.opened_by_user_id.in_(user_ids)) | (CommunityGovernanceCase.target_owner_user_id.in_(user_ids)))))
            session.execute(delete(Notification).where((Notification.recipient_user_id.in_(user_ids)) | (Notification.community_publication_id.in_(publication_ids)) | (Notification.community_case_id.in_(governance_case_ids))))
            session.execute(delete(CommunityGovernanceCase).where(CommunityGovernanceCase.id.in_(governance_case_ids)))
            session.execute(delete(CommunityGovernanceAction).where(CommunityGovernanceAction.target_owner_user_id.in_(user_ids)))
            if publication_ids:
                session.execute(update(CommunityPublication).where(CommunityPublication.id.in_(publication_ids)).values(public_version_number=None, pending_version_number=None))
                session.execute(delete(CommunityPublicationVersion).where(CommunityPublicationVersion.publication_id.in_(publication_ids)))
                session.execute(delete(CommunityPublication).where(CommunityPublication.id.in_(publication_ids)))
            if project_id is not None:
                session.execute(delete(Comment).where(Comment.project_id == project_id))
                session.execute(delete(Like).where(Like.project_id == project_id))
                session.execute(delete(Favorite).where(Favorite.project_id == project_id))
                session.execute(delete(ProjectView).where(ProjectView.project_id == project_id))
                session.execute(delete(project_tags).where(project_tags.c.project_id == project_id))
                session.execute(delete(Project).where(Project.id == project_id))
            session.execute(delete(CampusMembership).where(CampusMembership.user_id.in_(user_ids)))
            session.execute(delete(User).where(User.id.in_(user_ids)))
            session.execute(delete(Tag).where(Tag.name == f"P21-{marker}", ~Tag.projects.any()))
            session.commit()
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
