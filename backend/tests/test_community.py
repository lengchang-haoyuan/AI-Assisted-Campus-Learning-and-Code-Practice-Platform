import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_community_service, get_current_user
from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
from app.main import create_app
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.community import Comment, CommunityPublication, CommunityPublicationVersion, PublicationKind, PublicationStatus
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project, Tag
from app.models.user import User
from app.repositories.community import CommunityProjectRecord, CommunityRepository, TagRecord
from app.services.auth import UserIdentity
from app.services.community import CommentAuthorData, CommentData, CommentPage, CommunityOwnerData, CommunityProjectData, CommunityProjectPage, CommunityService, InteractionData, TagData, TagSummaryData
from tests.test_api_foundation import invoke_asgi

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def identity(user_id: int = 1) -> UserIdentity:
    return UserIdentity(id=user_id, username=f"user{user_id}", email=f"user{user_id}@example.com", avatar_url=None, bio=None, is_active=True, created_at=NOW)


def membership(user_id: int = 1, *, status: MembershipStatus = MembershipStatus.ACTIVE) -> CampusMembership:
    value = CampusMembership(user_id=user_id, role=CampusRole.STUDENT, status=status, verified_by_user_id=99, verified_at=NOW, revision=1)
    value.id = user_id
    return value


def make_project(*, owner_id: int = 1) -> Project:
    owner = User(username="owner", email="owner@example.com", password_hash="hash")
    owner.id = owner_id
    project = Project(owner_id=owner_id, name="校园失物招领", description="私人项目说明", difficulty=ProjectDifficulty.INTERMEDIATE, status=ProjectStatus.IN_PROGRESS, language="Python", framework="FastAPI", is_published=True, published_at=NOW)
    project.id = 7
    project.owner = owner
    project.tags = []
    project.view_count = 12
    project.created_at = NOW
    project.updated_at = NOW
    return project


def make_record(*, owner_id: int = 1) -> CommunityProjectRecord:
    publication = CommunityPublication(project_id=7, owner_user_id=owner_id, kind=PublicationKind.WORK, status=PublicationStatus.APPROVED, public_version_number=1, pending_version_number=None, revision=2, submitted_at=NOW, published_at=NOW)
    publication.id = 21
    version = CommunityPublicationVersion(publication_id=21, version_number=1, request_key="request_123", project_updated_at=NOW, kind=PublicationKind.WORK, name="校园失物招领", description="审核通过的固定说明", difficulty=ProjectDifficulty.INTERMEDIATE, project_status=ProjectStatus.IN_PROGRESS, language="Python", framework="FastAPI", frontend="Vue", backend="FastAPI", database="MySQL", repository_url=None, tag_names=["校园服务"], attribution="owner", source_license_statement="原创作品", ai_assistance_statement="AI 用于代码解释，作者已复核", human_review_statement=None, submitted_at=NOW)
    version.id = 31
    return CommunityProjectRecord(project=make_project(owner_id=owner_id), publication=publication, version=version, comment_count=2, like_count=3, favorite_count=1, liked=False, favorited=True)


def make_project_data() -> CommunityProjectData:
    return CommunityProjectData(id=7, publication_id=21, publication_kind=PublicationKind.WORK, publication_status=PublicationStatus.APPROVED, publication_version=1, name="校园失物招领", description="审核通过的固定说明", difficulty=ProjectDifficulty.INTERMEDIATE, status=ProjectStatus.IN_PROGRESS, language="Python", framework="FastAPI", frontend="Vue", backend="FastAPI", database="MySQL", repository_url=None, attribution="owner", source_license_statement="原创作品", ai_assistance_statement="AI 用于代码解释，作者已复核", human_review_statement=None, owner=CommunityOwnerData(id=1, username="owner", avatar_url=None), tags=[TagData(id=2, name="校园服务", slug="校园服务")], published_at=NOW, updated_at=NOW, view_count=12, comment_count=2, like_count=3, favorite_count=1, liked=False, favorited=True)


def publication_payload() -> dict[str, object]:
    version = {"version_number": 1, "kind": "work", "name": "校园失物招领", "description": "固定快照", "difficulty": "intermediate", "project_status": "in_progress", "language": "Python", "framework": "FastAPI", "frontend": "Vue", "backend": "FastAPI", "database": "MySQL", "repository_url": None, "tags": ["校园服务"], "attribution": "owner", "source_license_statement": "原创作品", "ai_assistance_statement": "未使用 AI", "human_review_statement": None, "submitted_at": NOW}
    return {"id": 21, "project_id": 7, "owner_user_id": 1, "kind": "work", "status": "pending_review", "public_version_number": None, "pending_version_number": 1, "revision": 1, "submitted_at": NOW, "reviewed_at": None, "published_at": None, "withdrawn_at": None, "taken_down_at": None, "public_version": None, "pending_version": version, "actions": []}


class CommunityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=CommunityRepository)
        self.repository.transaction.return_value = nullcontext()
        self.repository.campus_membership.return_value = membership()
        self.service = CommunityService(self.repository)

    def test_list_requires_active_campus_and_uses_public_snapshot(self) -> None:
        self.repository.count_published.return_value = 1
        self.repository.list_published.return_value = [make_record()]
        result = self.service.list_projects(identity(9), page=2, page_size=6, tag_slug="校园服务")
        self.repository.list_published.assert_called_once_with(9, offset=6, limit=6, tag_slug="校园服务")
        self.assertEqual(result.items[0].description, "审核通过的固定说明")
        self.assertEqual(result.items[0].publication_version, 1)
        self.repository.campus_membership.return_value = membership(9, status=MembershipStatus.SUSPENDED)
        with self.assertRaises(PermissionDeniedError):
            self.service.list_projects(identity(9), page=1, page_size=12, tag_slug=None)

    def test_missing_public_snapshot_is_not_exposed(self) -> None:
        self.repository.get_published.return_value = None
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_project(7, identity())

    def test_comment_delete_checks_active_author(self) -> None:
        comment = Comment(project_id=7, user_id=2, content="建议补充部署文档")
        comment.id = 4
        self.repository.comment.return_value = comment
        with self.assertRaises(PermissionDeniedError):
            self.service.delete_comment(4, identity(1))
        self.repository.campus_membership.return_value = membership(2)
        self.service.delete_comment(4, identity(2))
        self.repository.soft_delete_comment.assert_called_once()

    def test_interactions_require_visible_publication(self) -> None:
        self.repository.publication_by_project.return_value = make_record().publication
        self.repository.set_like.return_value = 3
        self.repository.set_favorite.return_value = 2
        self.assertEqual(self.service.set_like(7, identity(), active=True), InteractionData(active=True, count=3))
        self.assertEqual(self.service.set_favorite(7, identity(), active=False), InteractionData(active=False, count=2))

    def test_tags_require_membership(self) -> None:
        tag = Tag(name="Vue", slug="vue")
        tag.id = 2
        self.repository.list_tags.return_value = [TagRecord(tag=tag, project_count=5)]
        self.assertEqual(self.service.list_tags(identity()), [TagSummaryData(id=2, name="Vue", slug="vue", project_count=5)])


class CommunityAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.service = Mock()
        self.application.dependency_overrides[get_current_user] = lambda: identity()
        self.application.dependency_overrides[get_community_service] = lambda: self.service

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def request(self, method: str, path: str, body: dict[str, object] | None = None):
        return asyncio.run(invoke_asgi(self.application, method, path, body=body))

    def test_public_list_detail_and_tags_contract(self) -> None:
        project = make_project_data()
        self.service.list_projects.return_value = CommunityProjectPage(items=[project], total=1, page=1, page_size=12, total_pages=1)
        self.service.get_project.return_value = project
        self.service.list_tags.return_value = [TagSummaryData(id=2, name="校园服务", slug="校园服务", project_count=1)]
        listing = self.request("GET", "/api/v1/community/projects?tag=vue")
        detail = self.request("GET", "/api/v1/community/projects/7")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["items"][0]["publication_version"], 1)
        self.assertEqual(detail.json()["source_license_statement"], "原创作品")

    def test_publication_request_and_legacy_publish_contract(self) -> None:
        self.service.request_publication.return_value = publication_payload()
        created = self.request("POST", "/api/v1/projects/7/publication-requests", {"request_key": "request_123", "expected_project_updated_at": NOW.isoformat(), "kind": "work", "tags": ["Vue"], "attribution": "owner", "source_license_statement": "原创作品", "ai_assistance_statement": "未使用 AI"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["status"], "pending_review")
        self.service.reject_legacy_publish.side_effect = ConflictError("即时发布入口已停用")
        self.assertEqual(self.request("POST", "/api/v1/projects/7/publish", {"tags": ["Vue"]}).status_code, 409)

    def test_comment_validation_and_authentication(self) -> None:
        comment = CommentData(id=4, project_id=7, author=CommentAuthorData(id=1, username="viewer", avatar_url=None), content="项目结构很清楚", revision=1, created_at=NOW, updated_at=NOW, can_delete=True, can_report=False)
        self.service.create_comment.return_value = comment
        self.service.set_like.return_value = InteractionData(active=True, count=4)
        self.assertEqual(self.request("POST", "/api/v1/projects/7/comments", {"content": "项目结构很清楚"}).status_code, 201)
        self.assertEqual(self.request("POST", "/api/v1/projects/7/like").json(), {"active": True, "count": 4})
        self.assertEqual(self.request("POST", "/api/v1/projects/7/comments", {"content": "   "}).status_code, 422)
        self.application.dependency_overrides.clear()
        self.assertEqual(self.request("GET", "/api/v1/community/projects").status_code, 401)

    def test_report_and_moderation_decision_contract(self) -> None:
        pending_case = {
            "id": 51,
            "case_type": "report",
            "opened_by_user_id": 1,
            "target_owner_user_id": 2,
            "target_type": "project",
            "publication_id": 21,
            "publication_version_number": 1,
            "comment_id": None,
            "target_action_id": None,
            "reason": "作品说明包含无效链接",
            "target_excerpt": "校园失物招领",
            "status": "pending",
            "resolution_reason": None,
            "resolved_action_id": None,
            "revision": 1,
            "created_at": NOW,
            "resolved_at": None,
        }
        self.service.report.return_value = pending_case
        report = self.request(
            "POST",
            "/api/v1/community/reports",
            {
                "request_key": "report_123",
                "target_type": "project",
                "target_id": 7,
                "reason": "作品说明包含无效链接",
            },
        )
        self.assertEqual(report.status_code, 201)
        self.assertEqual(report.json()["status"], "pending")

        resolved_case = {
            **pending_case,
            "status": "accepted",
            "resolution_reason": "举报成立并下架",
            "resolved_action_id": 81,
            "revision": 2,
            "resolved_at": NOW,
        }
        self.service.decide_case.return_value = resolved_case
        decision = self.request(
            "POST",
            "/api/v1/community/moderation/cases/51/decisions",
            {
                "expected_revision": 1,
                "decision": "accept",
                "reason": "举报成立并下架",
            },
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
