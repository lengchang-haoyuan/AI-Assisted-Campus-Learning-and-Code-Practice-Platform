"""L4 HTTP/ASGI + 专用隔离 MySQL 主线验收；仅替换外部模型边界。"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from secrets import token_hex, token_urlsafe
import subprocess
from threading import Thread
from time import sleep
from unittest.mock import patch

from fastapi import FastAPI
import httpx
from sqlalchemy import create_engine, delete, func, inspect, select, text, update
from sqlalchemy.engine import make_url
import uvicorn

from app.ai.client import AIClient
from app.agents.learning_report import LearningReportAgent
from app.ai.provider import AIClientError, AICompletionRequest, AIFailureCategory, AIProvider, AIProviderResult, AIUsage
from app.core.config import get_security_settings, get_settings
from app.core.database import get_engine, get_session_factory
from app.core.security import SecurityService
from app.main import create_app
from app.models import Base
from app.models.ai import AIRequest, AIResult
from app.models.campus import AccountAudit, CampusInvitation, CampusMembership, PasswordReset
from app.models.community import Comment, CommunityGovernanceAction, CommunityGovernanceCase, CommunityPublication, CommunityPublicationVersion, Favorite, Like, ProjectView
from app.models.course import Course
from app.models.learning import DailyTask, LearningPlan, LearningRecord, LearningReport
from app.models.project import Project, Tag
from app.models.submission import Feedback, Notification, Submission, SubmissionVersion
from app.models.teaching import ClassMembership, TeachingAssignment, TeachingClass
from app.models.user import User
from app.repositories.campus import CampusRepository
from app.repositories.learning_report import LearningReportRepository
from app.services.campus import CampusService
from app.services.learning_report import LearningReportService
from scripts.verify_agents import ANALYSIS_RESULT, PROMPT_RESULT
from scripts.verify_workflow_engine import (
    architecture_result,
    requirements_result,
    tech_stack_result,
)


class IntegrationProvider(AIProvider):
    def __init__(self) -> None:
        self.report_mode = "wrong"
        self.report_source = None
        self.on_report = None
        self.fail_next_workflow = False
        self.results = [
            ANALYSIS_RESULT,
            PROMPT_RESULT,
            requirements_result(),
            tech_stack_result("Python"),
            architecture_result("FastAPI"),
            requirements_result(),
            tech_stack_result("Java"),
            architecture_result("Spring Boot"),
        ]

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        content = request.messages[-1].content
        marker = "<AGGREGATED_LEARNING_DATA>"
        if marker in content:
            source = json.loads(content.split(marker, 1)[1].split("</", 1)[0])
            self.report_source = source
            if self.on_report is not None:
                callback, self.on_report = self.on_report, None
                callback()
            if self.report_mode == "cancelled":
                raise asyncio.CancelledError
            if self.report_mode == "network":
                raise AIClientError("L4 controlled failure", category=AIFailureCategory.NETWORK)
            result = {
                "result_type": "learning_report",
                "summary": "这是基于验收数据的确定性报告，不是真实模型输出。",
                "achievement": ["已保存开发与学习记录"],
                "problems": ["需要继续积累长期学习样本"],
                "suggestions": ["按计划记录学习时长并复盘"],
                "structured_data": {
                    "performance_level": "steady",
                    "total_learning_minutes": source["learning"]["total_minutes"],
                    "active_days": source["learning"]["active_days"],
                    "task_completion_rate": source["tasks"]["completion_rate"],
                    "project_average_progress": source["projects"]["average_progress"],
                    "workflow_success_rate": source["workflows"]["success_rate"],
                    "ai_request_count": source["ai_usage"]["request_count"],
                    "focus_areas": ["项目实践"],
                    "recommended_weekly_minutes": 180,
                },
            }
            if self.report_mode == "wrong":
                result["structured_data"].update(
                    total_learning_minutes=999, active_days=7, task_completion_rate=12.5,
                    project_average_progress=1.0, workflow_success_rate=2.0, ai_request_count=99,
                )
            output = json.dumps(result, ensure_ascii=False)
            if self.report_mode == "invalid":
                output = "not-json"
        else:
            if self.fail_next_workflow:
                self.fail_next_workflow = False
                raise AIClientError("L4 controlled failure", category=AIFailureCategory.NETWORK)
            output = self.results.pop(0)
        return AIProviderResult(
            provider=self.name,
            model=request.model,
            content=output,
            finish_reason="stop",
            usage=AIUsage(prompt_tokens=100, completion_tokens=80, total_tokens=180),
        )


def cleanup(user_ids: list[int], tag_name: str, suffix: str) -> None:
    with get_session_factory()() as session:
        # 即使注册提交后响应失败，也只找回本次随机标识创建的主体。
        owned_ids = list(session.scalars(select(User.id).where(User.username.startswith(f"l4_verify_{suffix}_"))))
        if not set(user_ids).issubset(owned_ids):
            raise RuntimeError("清理主体与本次运行标识不一致")
        user_ids[:] = owned_ids
        memberships = select(CampusMembership.id).where(CampusMembership.user_id.in_(user_ids))
        class_ids = list(session.scalars(select(TeachingClass.id).where(TeachingClass.created_by_membership_id.in_(memberships))))
        submission_ids = list(session.scalars(select(Submission.id).where(Submission.class_id.in_(class_ids))))
        session.execute(delete(Notification).where(Notification.recipient_user_id.in_(user_ids)))
        session.execute(delete(Feedback).where(Feedback.submission_id.in_(submission_ids)))
        session.execute(update(Submission).where(Submission.id.in_(submission_ids)).values(latest_version_number=None))
        session.execute(delete(SubmissionVersion).where(SubmissionVersion.submission_id.in_(submission_ids)))
        session.execute(delete(Submission).where(Submission.id.in_(submission_ids)))
        session.execute(delete(TeachingAssignment).where(TeachingAssignment.class_id.in_(class_ids)))
        session.execute(delete(ClassMembership).where(ClassMembership.class_id.in_(class_ids)))
        session.execute(delete(TeachingClass).where(TeachingClass.id.in_(class_ids)))
        publication_ids = list(session.scalars(select(CommunityPublication.id).where(CommunityPublication.owner_user_id.in_(user_ids))))
        session.execute(delete(CommunityGovernanceCase).where(CommunityGovernanceCase.target_owner_user_id.in_(user_ids)))
        session.execute(delete(CommunityGovernanceAction).where(CommunityGovernanceAction.target_owner_user_id.in_(user_ids)))
        session.execute(update(CommunityPublication).where(CommunityPublication.id.in_(publication_ids)).values(public_version_number=None, pending_version_number=None))
        session.execute(delete(CommunityPublicationVersion).where(CommunityPublicationVersion.publication_id.in_(publication_ids)))
        session.execute(delete(CommunityPublication).where(CommunityPublication.id.in_(publication_ids)))
        for model, column in (
            (LearningReport, LearningReport.user_id),
            (AIRequest, AIRequest.user_id),
            (LearningRecord, LearningRecord.user_id),
            (DailyTask, DailyTask.user_id),
            (LearningPlan, LearningPlan.user_id),
            (Course, Course.owner_id),
            (Comment, Comment.user_id),
            (ProjectView, ProjectView.user_id),
            (Favorite, Favorite.user_id),
            (Like, Like.user_id),
            (Project, Project.owner_id),
        ):
            session.execute(delete(model).where(column.in_(user_ids)))
        session.execute(delete(Tag).where(Tag.name == tag_name, ~Tag.projects.any()))
        session.execute(delete(AccountAudit).where(AccountAudit.actor_user_id.in_(user_ids)))
        session.execute(delete(CampusInvitation).where(CampusInvitation.issued_by_user_id.in_(user_ids)))
        session.execute(delete(PasswordReset).where(PasswordReset.issued_by_user_id.in_(user_ids)))
        session.execute(delete(CampusMembership).where(CampusMembership.user_id.in_(user_ids)))
        session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()
        if session.scalar(select(User.id).where(User.id.in_(user_ids))) is not None:
            raise RuntimeError("P15 临时用户清理失败")
    remaining = database_counts()
    if any(remaining.values()):
        raise RuntimeError("隔离库仍有残留；保留现场，不扩大删除范围")
    print(json.dumps({"cleanup": "passed", "remaining_rows": sum(remaining.values())}))


def verify(application: FastAPI, user_ids: list[int], suffix: str, provider: IntegrationProvider, *, probe_cleanup: bool = False) -> dict:
    async def send(method: str, path: str, **kwargs) -> httpx.Response:
        transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, "/api/v1" + path, **kwargs)

    def call(method: str, path: str, expected: int = 200, **kwargs):
        if method == "POST" and path == "/auth/login":
            challenge = call("POST", "/auth/slider/challenge")
            sleep(0.6)
            verified = call("POST", "/auth/slider/verify", json={
                "challenge_id": challenge["challenge_id"], "position": 100,
            })
            kwargs["json"] = {**kwargs["json"], "slider_token": verified["slider_token"]}
        response = asyncio.run(send(method, path, **kwargs))
        if response.status_code != expected:
            code = response.json().get("error", {}).get("code", "unknown")
            raise AssertionError(
                f"{method} {path}: expected {expected}, got {response.status_code} ({code})"
            )
        if expected >= 400:
            assert set(response.json()["error"]) == {"code", "message", "request_id"}
        return response.json() if response.content else None

    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    headers = []
    accounts = []
    for index in range(1, 7):
        username = f"l4_verify_{suffix}_{index}"
        password = token_urlsafe(32)
        payload = {"username": username, "email": f"{username}@example.invalid", "password": password}
        user = call("POST", "/auth/register", 201, json=payload)
        user_ids.append(user["id"])
        accounts.append({"id": user["id"], "username": username, "password": password})
        assert "password_hash" not in user and "password" not in user
        if index == 1:
            call("POST", "/auth/register", 409, json=payload)
            call("POST", "/auth/login", 401, json={"identifier": username, "password": token_urlsafe(16)})
        token = call("POST", "/auth/login", json={"identifier": username, "password": password})
        headers.append({"Authorization": f"Bearer {token['access_token']}"})
    owner, other = headers[:2]
    call("GET", "/users/me", 401)
    assert call("GET", "/users/me", headers=owner)["id"] == user_ids[0]
    call("GET", "/community/projects", 403, headers=owner)
    print("L4 旧脚本前置条件复现：普通账号社区入口 403，符合当前校园权限")
    with get_session_factory()() as session:
        CampusService(CampusRepository(session), SecurityService(get_security_settings())).initialize_first_admin(
            user_id=user_ids[2], reason="L4 专用隔离库首管理员初始化",
        )
    admin_login = call("POST", "/auth/login", json={"identifier": accounts[2]["username"], "password": accounts[2]["password"]})
    headers[2] = {"Authorization": f"Bearer {admin_login['access_token']}"}
    for index, role in ((0, "student"), (1, "student"), (3, "teacher"), (4, "teacher")):
        invitation = call("POST", "/campus/invitations", 201, headers=headers[2], json={
            "target_user_id": user_ids[index], "role": role, "reason": "L4 虚构身份邀请",
        })
        call("POST", "/campus/invitations/redeem", headers=headers[index], json={"token": invitation["token"]})
        refreshed = call("POST", "/auth/login", json={"identifier": accounts[index]["username"], "password": accounts[index]["password"]})
        headers[index] = {"Authorization": f"Bearer {refreshed['access_token']}"}
        assert call("GET", "/campus/me", headers=headers[index])["membership"]["role"] == role
    owner, other = headers[:2]
    call("GET", "/community/projects", headers=owner)
    call("GET", "/community/projects", 403, headers=headers[5])
    call("GET", "/campus/admin/accounts", 403, headers=owner)
    if probe_cleanup:
        raise AssertionError("L4 controlled failure after identity fixtures")
    project = call("POST", "/projects", 201, headers=owner, json={
        "name": f"P15 校园学习实践 {suffix}", "difficulty": "intermediate",
        "language": "Python", "framework": "FastAPI", "frontend": "Vue 3",
        "backend": "FastAPI", "database": "MySQL", "status": "in_progress",
        "requirements": [{"title": "学习记录", "description": "保存记录并展示统计"}],
        "output_requirement": "给出开发步骤、知识点和验收方法，不执行代码",
    })
    project_path = f"/projects/{project['id']}"
    call("GET", project_path, 403, headers=other)
    call("PUT", project_path, 403, headers=other, json={"name": "越权更新"})
    call("DELETE", project_path, 403, headers=other)
    call("GET", "/projects/9223372036854775807", 404, headers=owner)
    call("GET", "/projects?page_size=101", 422, headers=owner)
    assert call("GET", "/projects", headers=owner)["total"] == 1
    context = call("POST", project_path + "/context", 201, headers=owner)
    assert context["values"]["language"] == "Python" and not context["is_stale"]
    call("GET", project_path + "/context", 403, headers=other)

    workflow = call("POST", "/workflows", 201, headers=owner, json={
        "project_id": project["id"], "name": "需求到架构的三节点验收",
    })
    workflow_path = f"/workflows/{workflow['id']}"
    node_types = ("requirements_analysis", "tech_stack_analysis", "architecture_design")
    graph_input = {
        "version": workflow["version"],
        "nodes": [{"node_key": f"node{index}", "node_type": kind, "name": kind,
                   "position_x": index * 280, "position_y": 80, "config": {}}
                  for index, kind in enumerate(node_types)],
        "edges": [{"source_node_key": f"node{index}", "target_node_key": f"node{index + 1}"}
                  for index in range(2)],
    }
    graph = call("PUT", workflow_path + "/graph", headers=owner, json=graph_input)
    restored = call("GET", workflow_path + "/graph", headers=owner)
    assert len(restored["nodes"]) == 3 and len(restored["edges"]) == 2
    assert restored["nodes"][1]["position_x"] == 280
    call("PUT", workflow_path + "/graph", 409, headers=owner, json=graph_input)
    cycle = {**graph_input, "version": graph["workflow"]["version"],
             "edges": graph_input["edges"] + [{"source_node_key": "node2", "target_node_key": "node0"}]}
    call("PUT", workflow_path + "/graph", 409, headers=owner, json=cycle)
    for endpoint, input_data in (
        ("project-analysis", {"focus": "校园学习项目的分层实现"}),
        ("prompt", {"task": "实现学习记录页面", "environment": "Windows 本地开发",
                    "target_directory": "frontend/src", "input_description": "记录表单",
                    "output_description": "经认证保存到后端", "coding_standards": ["不使用 any"],
                    "api_requirements": ["/api/v1/learning/records"]}),
    ):
        result = call("POST", f"/agents/{endpoint}", 201, headers=owner,
                      json={"project_id": project["id"], "input": input_data})
        assert result["status"] == "completed" and result["result"] is not None
        saved = call("GET", f"/agents/results/{result['request_id']}", headers=owner)
        assert saved["result"] == result["result"]
        call("GET", f"/agents/results/{result['request_id']}", 404, headers=other)
    agent_request_id = result["request_id"]
    run = call("POST", workflow_path + "/run", 201, headers=owner,
               json={"expected_version": graph["workflow"]["version"]})
    assert run["status"] == "completed" and len(run["nodes"]) == 3
    graph = call("GET", workflow_path + "/graph", headers=owner)
    call("POST", workflow_path + "/run", 409, headers=owner,
         json={"expected_version": graph["workflow"]["version"]})
    context = call("GET", project_path + "/context", headers=owner)
    changed = call("PUT", project_path + "/context", headers=owner, json={
        "expected_version": context["version"],
        "values": {"language": "Java", "framework": "Spring Boot", "backend": "Spring Boot"},
    })
    assert changed["stale_node_ids"]
    graph = call("GET", workflow_path + "/graph", headers=owner)
    assert any(node["node_type"] == "architecture_design" and node["status"] == "stale"
               for node in graph["nodes"])
    rerun = call("POST", workflow_path + "/run", 201, headers=owner,
                 json={"expected_version": graph["workflow"]["version"], "mode": "all"})
    assert rerun["status"] == "completed"
    assert call("GET", workflow_path + f"/runs/{rerun['id']}", headers=owner)["status"] == "completed"
    provider.fail_next_workflow = True
    graph = call("GET", workflow_path + "/graph", headers=owner)
    failed_run = call("POST", workflow_path + "/run", 201, headers=owner,
                      json={"expected_version": graph["workflow"]["version"], "mode": "all"})
    assert failed_run["status"] == "failed"
    assert call("GET", workflow_path + f"/runs/{failed_run['id']}", headers=owner)["status"] == "failed"
    provider.results.extend([requirements_result(), tech_stack_result("Java"), architecture_result("Spring Boot")])
    graph = call("GET", workflow_path + "/graph", headers=owner)
    recovered = call("POST", workflow_path + "/run", 201, headers=owner,
                     json={"expected_version": graph["workflow"]["version"]})
    assert recovered["status"] == "completed"
    call("GET", workflow_path + f"/runs/{recovered['id']}", 403, headers=other)
    print("L4 认证、校园邀请、Project、Workflow、Context、Agent、受控失败与续跑通过")

    course = call("POST", "/courses", 201, headers=owner, json={"name": f"软件工程 {suffix}"})
    plan = call("POST", "/learning/plans", 201, headers=owner, json={
        "title": "联调学习计划", "status": "active", "start_date": today, "end_date": today,
        "project_id": project["id"], "course_id": course["id"],
    })
    task = call("POST", "/learning/tasks", 201, headers=owner, json={
        "title": "验证完整链路", "scheduled_date": today, "plan_id": plan["id"],
        "project_id": project["id"], "estimated_minutes": 60,
    })
    call("POST", "/learning/tasks", 403, headers=other, json={
        "title": "越权关联", "scheduled_date": today, "plan_id": plan["id"],
    })
    call("POST", f"/workspace/tasks/{task['id']}/complete", headers=owner)
    assert call("GET", f"/learning/plans/{plan['id']}", headers=owner)["progress"] == 100
    for record_type in ("study", "project", "workflow", "ai", "course", "task"):
        call("POST", "/learning/records", 201, headers=owner, json={
            "title": f"P15 {record_type} 记录", "content": "人工验收创建的学习样本",
            "record_type": record_type, "duration_minutes": 10,
            "occurred_at": datetime.now(UTC).isoformat(), "project_id": project["id"],
            "course_id": course["id"], "task_id": task["id"],
        })
    assert call("GET", "/learning/records", headers=owner)["total"] == 6
    assert call("GET", "/learning/records", headers=other)["total"] == 0
    workspace_project = call("GET", f"/workspace/projects/{project['id']}", headers=owner)
    assert workspace_project["progress"] == 100
    call("GET", "/workspace/dashboard", headers=owner,
         params={"date": today, "utc_offset_minutes": 480})
    call("PUT", project_path, headers=owner, json={"status": "completed"})
    for days in (7, 30):
        trend = call("GET", "/statistics/trend", headers=owner,
                     params={"days": days, "timezone_offset_minutes": 480})
        assert len(trend["items"]) == days
    call("GET", "/statistics/today", headers=owner)
    call("GET", "/statistics/projects", headers=owner)
    call("GET", "/statistics/tech-stacks", headers=owner)
    report_input = {"period_start": today, "period_end": today, "timezone_offset_minutes": 480}
    def add_during_generation() -> None:
        with get_session_factory()() as session:
            session.add(LearningRecord(user_id=user_ids[0], title="L4 生成期间新增记录", record_type="study",
                                       duration_minutes=5, occurred_at=datetime.now(UTC), project_id=project["id"]))
            session.commit()
    provider.on_report = add_during_generation
    report = call("POST", "/learning-reports", 201, headers=owner, json=report_input)
    assert report["status"] == "completed", "报告生成失败，未伪造成功"
    assert report["structured_data"]["total_learning_minutes"] == 60
    assert report["structured_data"]["project_average_progress"] == workspace_project["progress"], \
        "工作台与学习报告的项目进度不一致"
    assert call("GET", f"/learning-reports/{report['id']}", headers=owner)["summary"] == report["summary"]
    call("GET", f"/learning-reports/{report['id']}", 404, headers=other)
    call("POST", "/learning-reports", 409, headers=owner, json=report_input)
    verify_saved_report(report, provider.report_source)
    with get_session_factory()() as session:
        assert session.scalar(select(func.sum(LearningRecord.duration_minutes)).where(LearningRecord.user_id == user_ids[0])) == 65
    for mode in ("invalid", "network", "cancelled"):
        provider.report_mode = mode
        if mode == "cancelled":
            # HTTP 中断没有成功响应契约；在真实 Service + MySQL 边界验证取消传播与失败落库。
            try:
                with get_session_factory()() as session:
                    client = AIClient(provider, total_timeout_seconds=5, max_retries=0,
                                      retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
                    agent = LearningReportAgent(client, model="l4-fake", max_tokens=1200, temperature=0.1)
                    asyncio.run(LearningReportService(LearningReportRepository(session), agent).generate(
                        user_ids[1], period_start=datetime.fromisoformat(today).date(),
                        period_end=datetime.fromisoformat(today).date(), timezone_offset_minutes=480,
                    ))
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("取消未向调用方传播")
            failed = call("GET", "/learning-reports", headers=other)["items"][0]
        else:
            failed = call("POST", "/learning-reports", 201, headers=other, json=report_input)
        assert failed["status"] == "failed" and failed["structured_data"] is None
        expected_code = {"invalid": "agent_output_invalid", "network": "network", "cancelled": "cancelled"}[mode]
        assert failed["error"]["code"] == expected_code
        with get_session_factory()() as session:
            saved_failed = session.get(LearningReport, failed["id"])
            assert saved_failed.status.value == "failed" and saved_failed.ai_result_id is None
    provider.report_mode = "wrong"
    empty_report = call("POST", "/learning-reports", 201, headers=other, json=report_input)
    assert empty_report["id"] == failed["id"] and empty_report["status"] == "completed"
    verify_saved_report(empty_report, provider.report_source)
    assert all(empty_report["structured_data"][key] == 0 for key in FACT_FIELDS)
    print("L4 L3 同次 Source、六事实、双份持久化、全零、失败/取消/重试通过")

    fresh_project = call("GET", project_path, headers=owner)
    publication = call("POST", project_path + "/publication-requests", 201, headers=owner, json={
        "request_key": f"publish_{suffix}", "expected_project_updated_at": fresh_project["updated_at"],
        "kind": "work", "tags": [f"p15_{suffix}"], "attribution": "L4 虚构作者",
        "source_license_statement": "隔离验收自建样本", "ai_assistance_statement": "仅使用确定性 Fake Provider",
    })
    call("GET", f"/community/projects/{project['id']}", 404, headers=other)
    decision_path = f"/community/moderation/publications/{publication['id']}/decisions"
    decision = {"expected_revision": publication["revision"], "decision": "approve", "reason": "L4 虚构作品审核通过"}
    call("POST", decision_path, 403, headers=other, json=decision)
    publication = call("POST", decision_path, headers=headers[2], json=decision)
    assert publication["status"] == "approved"
    call("POST", project_path + "/view", headers=other)
    for action in ("like", "favorite"):
        first = call("POST", project_path + f"/{action}", headers=other)
        second = call("POST", project_path + f"/{action}", headers=other)
        assert first == second and first["active"]
    comment = call("POST", project_path + "/comments", 201, headers=other,
                   json={"content": "P15 联调样本：实践步骤清晰"})
    detail = call("GET", f"/community/projects/{project['id']}", headers=other)
    assert detail["view_count"] == 1 and detail["comment_count"] == 1
    assert detail["liked"] and detail["favorited"]
    call("PUT", project_path, headers=owner, json={"description": "L4 审核后私人变更"})
    assert call("GET", f"/community/projects/{project['id']}", headers=other)["description"] == detail["description"]
    print("L4 社区申请、管理员审核、公开快照与互动通过")
    learning = verify_learning_constraints(call, owner, other, user_ids[0], project["id"], today)
    teaching = verify_teaching(call, headers, user_ids, learning["practice_project_id"], learning["practice_task_id"], suffix)
    return {"accounts": accounts, "project_id": project["id"], "workflow_id": workflow["id"],
            "agent_request_id": agent_request_id, "report_id": report["id"],
            "report_facts": report["structured_data"], **learning, **teaching}


FACT_FIELDS = (
    "total_learning_minutes", "active_days", "task_completion_rate",
    "project_average_progress", "workflow_success_rate", "ai_request_count",
)


def verify_saved_report(response: dict, source: dict) -> None:
    expected = (
        source["learning"]["total_minutes"], source["learning"]["active_days"],
        source["tasks"]["completion_rate"], source["projects"]["average_progress"],
        source["workflows"]["success_rate"], source["ai_usage"]["request_count"],
    )
    assert tuple(response["structured_data"][key] for key in FACT_FIELDS) == expected
    with get_session_factory()() as session:
        report = session.get(LearningReport, response["id"])
        result = session.get(AIResult, report.ai_result_id)
        assert report.structured_data == result.structured_result["structured_data"] == response["structured_data"]
        canonical = json.dumps(result.structured_result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        assert result.content_hash == sha256(canonical.encode("utf-8")).hexdigest()
        assert report.status.value == "completed"


def learning_snapshot(user_id: int) -> dict:
    # 独立 Session 重查全行，失败不能留下标题、时间戳或关联等部分修改。
    with get_session_factory()() as session:
        return {
            model.__tablename__: [dict(row) for row in session.execute(
                select(model.__table__).where(model.user_id == user_id).order_by(model.id)
            ).mappings()]
            for model in (LearningPlan, DailyTask)
        }


def verify_learning_constraints(call, owner: dict, other: dict, user_id: int, project_id: int, today: str) -> dict:
    def reject(method: str, path: str, values: dict | None = None) -> None:
        before = learning_snapshot(user_id)
        options = {"json": values} if values is not None else {}
        rejected = call(method, path, 409, headers=owner, **options)
        assert rejected["error"]["code"] == "conflict"
        assert learning_snapshot(user_id) == before

    def new_plan(title: str, **values) -> dict:
        return call("POST", "/learning/plans", 201, headers=owner, json={"title": title, "status": "active", **values})

    def new_task(title: str, **values) -> dict:
        return call("POST", "/learning/tasks", 201, headers=owner, json={"title": title, "scheduled_date": today, **values})

    completed_plan = new_plan("L4 L1 终态计划")
    first = new_task("L4 学习入口完成", plan_id=completed_plan["id"])
    second = new_task("L4 工作台入口完成", plan_id=completed_plan["id"])
    plan_path = f"/learning/plans/{completed_plan['id']}"
    assert call("GET", plan_path, headers=owner)["progress"] == 0
    call("POST", f"/learning/tasks/{first['id']}/complete", headers=owner)
    assert call("GET", plan_path, headers=owner)["progress"] == 50
    call("POST", f"/workspace/tasks/{second['id']}/complete", headers=owner)
    assert call("GET", plan_path, headers=owner)["progress"] == 100
    call("PUT", plan_path, headers=owner, json={"status": "completed"})
    cancelled_plan = new_plan("L4 L1 取消计划")
    pending = new_task("L4 取消计划的待办", plan_id=cancelled_plan["id"])
    call("PUT", f"/learning/plans/{cancelled_plan['id']}", headers=owner, json={"status": "cancelled"})
    active_plan = new_plan("L4 L1 活动计划")
    movable = new_task("L4 可移动待办")
    for plan, task, progress in ((completed_plan, first, 100), (cancelled_plan, pending, 0)):
        reject("POST", "/learning/tasks", {"title": "非法新增", "scheduled_date": today, "plan_id": plan["id"]})
        reject("PUT", f"/learning/tasks/{movable['id']}", {"title": "不得部分保存", "plan_id": plan["id"]})
        reject("PUT", f"/learning/tasks/{task['id']}", {"plan_id": None})
        reject("PUT", f"/learning/tasks/{task['id']}", {"plan_id": active_plan["id"]})
        reject("DELETE", f"/learning/tasks/{task['id']}")
        if progress == 0:
            reject("POST", f"/learning/tasks/{task['id']}/complete")
            reject("POST", f"/workspace/tasks/{task['id']}/complete")
            reject("PUT", f"/learning/tasks/{task['id']}", {"status": "completed"})
        else:
            before = learning_snapshot(user_id)
            call("POST", f"/learning/tasks/{task['id']}/complete", headers=owner)
            call("POST", f"/workspace/tasks/{task['id']}/complete", headers=owner)
            assert learning_snapshot(user_id) == before
        call("PUT", f"/learning/tasks/{task['id']}", headers=owner, json={"title": "L4 合法历史标题编辑"})
        assert call("GET", f"/learning/plans/{plan['id']}", headers=owner)["progress"] == progress
    call("PUT", f"/learning/tasks/{movable['id']}", headers=owner, json={"plan_id": active_plan["id"]})
    draft_plan = new_plan("L4 L1 草稿计划", status="draft")
    call("PUT", f"/learning/tasks/{movable['id']}", headers=owner, json={"plan_id": draft_plan["id"]})
    call("POST", f"/learning/tasks/{movable['id']}/complete", headers=owner)
    assert call("GET", f"/learning/plans/{draft_plan['id']}", headers=owner)["progress"] == 100
    call("DELETE", f"/learning/tasks/{movable['id']}", 204, headers=owner)
    assert call("GET", f"/learning/plans/{draft_plan['id']}", headers=owner)["progress"] == 0
    print("L4 L1 终态拒绝/幂等/历史编辑及活动/草稿进度，独立 Session 刷新通过")

    day = datetime.fromisoformat(today).date()
    before_day, after_day = (day - timedelta(days=2)).isoformat(), (day + timedelta(days=2)).isoformat()
    project_b = call("POST", "/projects", 201, headers=owner, json={"name": "L4 待实践项目 B", "difficulty": "beginner", "status": "in_progress"})
    constrained = new_plan("L4 L2 项目日期计划", project_id=project_id, start_date=before_day, end_date=after_day)
    constrained_path = f"/learning/plans/{constrained['id']}"
    task = new_task("L4 尚待本人完成的实践", plan_id=constrained["id"])
    assert task["project"]["id"] == project_id
    reject("PUT", constrained_path, {"title": "不得部分修改", "project_id": project_b["id"]})
    reject("PUT", constrained_path, {"start_date": (day + timedelta(days=1)).isoformat()})
    reject("PUT", constrained_path, {"end_date": (day - timedelta(days=1)).isoformat()})
    for values in (
        {"project_id": project_id, "start_date": before_day, "end_date": after_day},
        {"start_date": today, "end_date": today},
        {"start_date": before_day, "end_date": after_day},
        {"project_id": None, "start_date": None, "end_date": None},
    ):
        call("PUT", constrained_path, headers=owner, json=values)
    with get_session_factory()() as session:
        saved = session.get(LearningPlan, constrained["id"])
        assert saved.project_id is None and saved.start_date is None and saved.end_date is None
        assert session.get(DailyTask, task["id"]).project_id == project_id
    call("PUT", f"/learning/tasks/{task['id']}", headers=owner, json={"project_id": project_b["id"]})
    call("PUT", constrained_path, headers=owner, json={"project_id": project_b["id"], "start_date": today, "end_date": today})
    empty = new_plan("L4 L2 无任务计划", project_id=project_id)
    call("PUT", f"/learning/plans/{empty['id']}", headers=owner, json={"project_id": project_b["id"], "start_date": today, "end_date": today})
    snapshot = learning_snapshot(user_id)
    call("PUT", constrained_path, 403, headers=other, json={"title": "越权"})
    call("POST", "/learning/tasks", 403, headers=other, json={"title": "越权关联", "scheduled_date": today, "plan_id": constrained["id"]})
    call("PUT", f"/learning/tasks/{task['id']}", 403, headers=other, json={"project_id": project_b["id"]})
    assert learning_snapshot(user_id) == snapshot
    print("L4 L2 项目/日期拒绝无部分保存，范围/null/同值/重新关联及所有权通过")
    return {"terminal_plan_id": completed_plan["id"], "practice_plan_id": constrained["id"],
            "practice_project_id": project_b["id"], "practice_task_id": task["id"]}


def verify_teaching(call, headers: list[dict], user_ids: list[int], project_id: int, task_id: int, suffix: str) -> dict:
    student, other_student, admin, teacher, other_teacher, outsider = headers
    classes = []
    for teacher_header, student_header, label in ((teacher, student, "A"), (other_teacher, other_student, "B")):
        classroom = call("POST", "/campus/classes", 201, headers=teacher_header, json={
            "name": f"L4 虚构教学班 {label}", "course_title": "软件工程实践", "term_label": "2026 秋季",
        })
        membership = call("GET", "/campus/me", headers=student_header)["membership"]
        call("POST", f"/campus/classes/{classroom['id']}/members", 201, headers=teacher_header,
             json={"campus_membership_id": membership["id"], "member_role": "student"})
        classes.append(classroom)
    class_path = f"/campus/classes/{classes[0]['id']}"
    call("GET", class_path, 404, headers=other_student)
    call("GET", class_path, 404, headers=other_teacher)
    assignment = call("POST", class_path + "/assignments", 201, headers=teacher, json={
        "title": "L4 字符串测试与修订", "instructions": "完成字符串实践并根据教师反馈补齐测试说明。",
        "learning_objectives": ["理解验证与修订"], "acceptance_criteria": ["记录空字符串与中文样例"],
        "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    })
    assignment_path = f"/campus/assignments/{assignment['id']}"
    call("GET", assignment_path, 404, headers=student)
    published = call("POST", assignment_path + "/publish", headers=teacher, json={"expected_revision": assignment["revision"]})
    assert published["status"] == "published"
    assert call("GET", assignment_path, headers=student)["status"] == "published"
    call("GET", assignment_path, 404, headers=other_student)
    with get_session_factory()() as session:
        before_minutes = session.scalar(select(func.sum(LearningRecord.duration_minutes)).where(LearningRecord.user_id == user_ids[0]))
        project_status = session.get(Project, project_id).status
        task_status = session.get(DailyTask, task_id).status
    v1 = call("POST", assignment_path + "/submissions", 201, headers=student, json={
        "request_key": f"submit_{suffix}_v1", "expected_latest_version": 0,
        "summary": "L4 V1：完成基础字符串实践，待补空字符串测试。", "source_project_id": project_id,
    })
    submission_path = f"/campus/submissions/{v1['id']}"
    call("GET", submission_path, 404, headers=other_student)
    call("GET", submission_path, 404, headers=other_teacher)
    returned = call("POST", submission_path + "/versions/1/feedback", 201, headers=teacher, json={
        "expected_revision": v1["revision"], "decision": "return", "comment": "L4 请补充空字符串和中文测试。",
    })
    assert call("GET", submission_path, headers=student)["latest_version"]["status"] == "returned"
    notes = call("GET", "/notifications", headers=student)["items"]
    assert any(item["feedback_id"] == returned["id"] for item in notes)
    v2 = call("POST", assignment_path + "/submissions", 201, headers=student, json={
        "request_key": f"submit_{suffix}_v2", "expected_latest_version": 1,
        "summary": "L4 V2：已补齐空字符串和中文测试，并记录结果。", "source_project_id": project_id,
    })
    accepted = call("POST", submission_path + "/versions/2/feedback", 201, headers=teacher, json={
        "expected_revision": v2["revision"], "decision": "accept", "comment": "L4 两类测试齐全，确认通过。",
    })
    for actor in (student, teacher):
        history = call("GET", submission_path + "/versions", headers=actor)["items"]
        assert [(item["version_number"], item["status"]) for item in history] == [(2, "accepted"), (1, "returned")]
        assert history[0]["feedback"]["id"] == accepted["id"]
        assert history[1]["feedback"]["id"] == returned["id"]
    notes = call("GET", "/notifications", headers=student)["items"]
    accepted_note = next(item for item in notes if item["feedback_id"] == accepted["id"])
    call("POST", f"/notifications/{accepted_note['id']}/read", 404, headers=other_student)
    call("POST", f"/notifications/{accepted_note['id']}/read", headers=student)
    with get_session_factory()() as session:
        feedback = session.get(Feedback, accepted["id"])
        record = session.get(LearningRecord, feedback.learning_record_id)
        assert record.duration_minutes is None and record.task_id is None
        assert session.scalar(select(func.sum(LearningRecord.duration_minutes)).where(LearningRecord.user_id == user_ids[0])) == before_minutes
        assert session.get(Project, project_id).status == project_status
        assert session.get(DailyTask, task_id).status == task_status
        assert session.get(Notification, accepted_note["id"]).read_at is not None
    print("L4 教学草稿/发布、V1退回通知、V2通过、双方历史与跨班隔离通过；未伪造时长/个人完成")
    return {"class_id": classes[0]["id"], "assignment_id": assignment["id"], "submission_id": v1["id"]}


def database_counts() -> dict[str, int]:
    with get_engine().connect() as connection:
        return {name: int(connection.scalar(select(func.count()).select_from(table)))
                for name, table in Base.metadata.tables.items()}


class IsolationPreconditionError(RuntimeError):
    """只包含可公开的隔离环境前置条件错误。"""


def configure_isolated_database(database: str, *, initialize: bool) -> None:
    if re.fullmatch(r"scholarhub_l4_[a-z0-9_]{1,40}", database) is None:
        raise IsolationPreconditionError("必须显式指定 scholarhub_l4_ 前缀的专用隔离库")
    configured = get_settings().database_url
    if not configured:
        raise IsolationPreconditionError("本机未配置数据库连接")
    url = make_url(configured)
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise IsolationPreconditionError("本验收仅获准使用本机 MySQL")
    if initialize:
        server = create_engine(url.set(database=None), hide_parameters=True)
        try:
            with server.connect() as connection:
                exists = connection.scalar(text("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:name"), {"name": database})
                if exists:
                    raise IsolationPreconditionError("专用库已存在，拒绝重新初始化；确认空库后省略 --initialize")
                connection.exec_driver_sql(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        finally:
            server.dispose()
    os.environ["DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
    os.environ["JWT_SECRET"] = token_urlsafe(48)
    get_settings.cache_clear()
    get_security_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    if initialize:
        Base.metadata.create_all(get_engine())
    if set(inspect(get_engine()).get_table_names()) != set(Base.metadata.tables):
        raise IsolationPreconditionError("隔离库表集合不完整，不自动迁移已有库")
    if any(database_counts().values()):
        raise IsolationPreconditionError("隔离库不是空库；拒绝写入或自动清空")
    print(json.dumps({"environment": "dedicated-local-mysql", "database": database, "initial_rows": 0}))


def run_browser(application: FastAPI, manifest: dict) -> None:
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=8001, log_level="warning", access_log=False))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            if server.started:
                break
            sleep(0.1)
        if not server.started:
            raise RuntimeError("隔离 HTTP 服务未能启动")
        subprocess.run(
            ["node", "scripts/verify-l4-mainline.cjs"],
            cwd=Path(__file__).resolve().parents[2] / "frontend",
            input=json.dumps(manifest), text=True, encoding="utf-8", check=True,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="已明确确认的本机专用隔离库名")
    parser.add_argument("--initialize", action="store_true", help="仅首次创建不存在的专用库和现有 Models 表结构")
    parser.add_argument("--browser", action="store_true", help="连接已启动的前端预览，另验真实 API 浏览器刷新")
    parser.add_argument("--probe-cleanup", action="store_true", help="身份样本创建后主动失败，检验异常路径清理；预期退出 1")
    args = parser.parse_args()
    user_ids: list[int] = []
    suffix = token_hex(5)
    prepared = False
    try:
        configure_isolated_database(args.database, initialize=args.initialize)
        from scripts.verify_database_schema import main as verify_schema
        if verify_schema() != 0:
            raise AssertionError("隔离数据库结构检查失败")
        prepared = True
        provider = IntegrationProvider()
        fake_client = AIClient(provider, total_timeout_seconds=5, max_retries=0,
                               retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
        with patch("app.api.deps.build_ai_client", return_value=fake_client):
            application = create_app()
            manifest = verify(application, user_ids, suffix, provider, probe_cleanup=args.probe_cleanup)
            print(json.dumps({"api_mainline": "passed", "run_marker": suffix,
                              "resources": {key: value for key, value in manifest.items() if key.endswith("_id")},
                              "row_counts": database_counts()}, ensure_ascii=False))
            if args.browser:
                run_browser(application, manifest)
        return 0
    except Exception as exc:
        import traceback
        location = traceback.extract_tb(exc.__traceback__)[-1]
        detail = str(exc) if isinstance(exc, (AssertionError, IsolationPreconditionError)) else "详情按阶段定位，未输出连接/SQL参数"
        error_args = getattr(getattr(exc, "orig", None), "args", ())
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "database_error_code": error_args[0] if error_args and isinstance(error_args[0], int) else None,
                          "location": f"{Path(location.filename).name}:{location.lineno}", "detail": detail}, ensure_ascii=False))
        return 1
    finally:
        if prepared:
            try:
                cleanup(user_ids, f"p15_{suffix}", suffix)
            except Exception as exc:
                print(json.dumps({"cleanup": "failed", "error_type": type(exc).__name__,
                                  "action": "保留残留数据，按本次运行标识定位，不自动扩大清理"}, ensure_ascii=False))
                raise SystemExit(1) from None


if __name__ == "__main__":
    raise SystemExit(main())
