import asyncio
from datetime import UTC, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_community_service, get_current_user
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.main import create_app
from app.models.community import Comment
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project, Tag
from app.models.user import User
from app.repositories.community import CommunityProjectRecord, CommunityRepository, TagRecord
from app.services.auth import UserIdentity
from app.services.community import (
    CommentAuthorData,
    CommentData,
    CommentPage,
    CommunityOwnerData,
    CommunityProjectData,
    CommunityProjectPage,
    CommunityService,
    InteractionData,
    TagData,
    TagSummaryData,
)
from tests.test_api_foundation import invoke_asgi

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def make_project(*, owner_id: int = 1, published: bool = True) -> Project:
    owner = User(
        username="owner",
        email="owner@example.com",
        password_hash="hash",
    )
    owner.id = owner_id
    project = Project(
        owner_id=owner_id,
        name="校园失物招领",
        description="用 FastAPI 和 Vue 构建的校园项目",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        language="Python",
        framework="FastAPI",
        is_published=published,
        published_at=NOW if published else None,
    )
    project.id = 7
    project.owner = owner
    project.tags = []
    project.view_count = 12
    project.created_at = NOW
    project.updated_at = NOW
    return project


def make_record(*, owner_id: int = 1) -> CommunityProjectRecord:
    return CommunityProjectRecord(
        project=make_project(owner_id=owner_id),
        comment_count=2,
        like_count=3,
        favorite_count=1,
        liked=False,
        favorited=True,
    )


def make_project_data() -> CommunityProjectData:
    return CommunityProjectData(
        id=7,
        name="校园失物招领",
        description="用 FastAPI 和 Vue 构建的校园项目",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        language="Python",
        framework="FastAPI",
        frontend="Vue",
        backend="FastAPI",
        database="MySQL",
        owner=CommunityOwnerData(id=1, username="owner", avatar_url=None),
        tags=[TagData(id=2, name="校园服务", slug="校园服务")],
        published_at=NOW,
        updated_at=NOW,
        view_count=12,
        comment_count=2,
        like_count=3,
        favorite_count=1,
        liked=False,
        favorited=True,
    )


class CommunityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=CommunityRepository)
        self.service = CommunityService(self.repository)

    def test_list_projects_is_published_tag_scoped_and_paginated(self) -> None:
        self.repository.count_published.return_value = 1
        self.repository.list_published.return_value = [make_record()]

        result = self.service.list_projects(
            9, page=2, page_size=6, tag_slug="校园服务"
        )

        self.repository.count_published.assert_called_once_with("校园服务")
        self.repository.list_published.assert_called_once_with(
            9, offset=6, limit=6, tag_slug="校园服务"
        )
        self.assertEqual(result.total_pages, 1)
        self.assertEqual(result.items[0].favorite_count, 1)

    def test_publish_requires_owner_and_returns_database_state(self) -> None:
        project = make_project(published=False)
        self.repository.get_project.return_value = project
        self.repository.get_published.return_value = make_record()

        result = self.service.publish_project(7, 1, ["Vue", "校园服务"])

        self.repository.publish.assert_called_once_with(
            project, ["Vue", "校园服务"]
        )
        self.assertEqual(result.id, 7)

        project.owner_id = 2
        with self.assertRaises(PermissionDeniedError):
            self.service.publish_project(7, 1, [])

    def test_missing_unpublished_project_is_not_exposed(self) -> None:
        self.repository.get_published.return_value = None
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_project(7, 1)

    def test_comment_delete_checks_comment_owner(self) -> None:
        comment = Comment(project_id=7, user_id=2, content="建议补充部署文档")
        comment.id = 4
        self.repository.get_comment.return_value = comment

        with self.assertRaises(PermissionDeniedError):
            self.service.delete_comment(4, 1)
        self.repository.soft_delete_comment.assert_not_called()

        self.service.delete_comment(4, 2)
        self.repository.soft_delete_comment.assert_called_once_with(comment)

    def test_like_and_favorite_return_idempotent_repository_result(self) -> None:
        self.repository.get_published.return_value = make_record()
        self.repository.set_like.return_value = 3
        self.repository.set_favorite.return_value = 2

        like = self.service.set_like(7, 1, active=True)
        favorite = self.service.set_favorite(7, 1, active=False)

        self.assertEqual(like, InteractionData(active=True, count=3))
        self.assertEqual(favorite, InteractionData(active=False, count=2))

    def test_tags_only_report_published_project_counts(self) -> None:
        tag = Tag(name="Vue", slug="vue")
        tag.id = 2
        self.repository.list_tags.return_value = [TagRecord(tag=tag, project_count=5)]

        self.assertEqual(
            self.service.list_tags(),
            [TagSummaryData(id=2, name="Vue", slug="vue", project_count=5)],
        )


class CommunityAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.service = Mock()
        self.application.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="viewer",
            email="viewer@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.application.dependency_overrides[get_community_service] = lambda: self.service

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
    ):
        return asyncio.run(invoke_asgi(self.application, method, path, body=body))

    def test_list_detail_and_tags_map_service_results(self) -> None:
        project = make_project_data()
        self.service.list_projects.return_value = CommunityProjectPage(
            items=[project], total=1, page=1, page_size=12, total_pages=1
        )
        self.service.get_project.return_value = project
        self.service.list_tags.return_value = [
            TagSummaryData(id=2, name="校园服务", slug="校园服务", project_count=1)
        ]

        listing = self.request("GET", "/api/v1/community/projects?tag=vue")
        detail = self.request("GET", "/api/v1/community/projects/7")
        tags = self.request("GET", "/api/v1/community/tags")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["items"][0]["like_count"], 3)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(tags.json()[0]["project_count"], 1)

    def test_publish_comment_and_interactions_have_stable_responses(self) -> None:
        project = make_project_data()
        comment = CommentData(
            id=4,
            project_id=7,
            author=CommentAuthorData(id=1, username="viewer", avatar_url=None),
            content="项目结构很清楚",
            created_at=NOW,
            updated_at=NOW,
            can_delete=True,
        )
        self.service.publish_project.return_value = project
        self.service.create_comment.return_value = comment
        self.service.list_comments.return_value = CommentPage(
            items=[comment], total=1, page=1, page_size=20, total_pages=1
        )
        self.service.set_like.return_value = InteractionData(active=True, count=4)
        self.service.set_favorite.return_value = InteractionData(active=False, count=1)
        self.service.record_view.return_value = 13

        published = self.request(
            "POST", "/api/v1/projects/7/publish", {"tags": ["Vue"]}
        )
        created = self.request(
            "POST", "/api/v1/projects/7/comments", {"content": "项目结构很清楚"}
        )
        comments = self.request("GET", "/api/v1/projects/7/comments")
        liked = self.request("POST", "/api/v1/projects/7/like")
        unfavorited = self.request("DELETE", "/api/v1/projects/7/favorite")
        viewed = self.request("POST", "/api/v1/projects/7/view")

        self.assertEqual(published.status_code, 200)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(comments.json()["items"][0]["can_delete"], True)
        self.assertEqual(liked.json(), {"active": True, "count": 4})
        self.assertEqual(unfavorited.json(), {"active": False, "count": 1})
        self.assertEqual(viewed.json(), {"view_count": 13})

    def test_validation_and_authentication_boundaries(self) -> None:
        invalid_comment = self.request(
            "POST", "/api/v1/projects/7/comments", {"content": "   "}
        )
        invalid_tags = self.request(
            "POST", "/api/v1/projects/7/publish", {"tags": ["x" * 51]}
        )
        self.assertEqual(invalid_comment.status_code, 422)
        self.assertEqual(invalid_tags.status_code, 422)

        self.application.dependency_overrides.clear()
        unauthenticated = self.request("GET", "/api/v1/community/projects")
        self.assertEqual(unauthenticated.status_code, 401)


if __name__ == "__main__":
    unittest.main()
