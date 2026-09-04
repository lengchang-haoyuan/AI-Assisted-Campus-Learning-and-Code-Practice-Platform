"""P15 HTTP/ASGI + MySQL 全链路验收；默认仅替换外部模型边界。"""

import argparse
import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta, timezone
import json
from secrets import token_hex, token_urlsafe
from time import sleep
from unittest.mock import patch

from fastapi import FastAPI
import httpx
from sqlalchemy import delete, select

from app.ai.client import AIClient
from app.ai.provider import AICompletionRequest, AIProvider, AIProviderResult, AIUsage
from app.core.config import get_ai_settings
from app.core.database import get_session_factory
from app.main import create_app
from app.models.ai import AIRequest
from app.models.community import Comment, Favorite, Like, ProjectView
from app.models.course import Course
from app.models.learning import DailyTask, LearningPlan, LearningRecord, LearningReport
from app.models.project import Project, Tag
from app.models.user import User
from scripts.verify_agents import ANALYSIS_RESULT, PROMPT_RESULT
from scripts.verify_workflow_engine import (
    architecture_result,
    requirements_result,
    tech_stack_result,
)


class IntegrationProvider(AIProvider):
    def __init__(self) -> None:
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
            output = json.dumps(result, ensure_ascii=False)
        else:
            output = self.results.pop(0)
        return AIProviderResult(
            provider=self.name,
            model=request.model,
            content=output,
            finish_reason="stop",
            usage=AIUsage(prompt_tokens=100, completion_tokens=80, total_tokens=180),
        )


def cleanup(user_ids: list[int], tag_name: str) -> None:
    if not user_ids:
        return
    with get_session_factory()() as session:
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
        session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()
        if session.scalar(select(User.id).where(User.id.in_(user_ids))) is not None:
            raise RuntimeError("P15 临时用户清理失败")
    print("P15 临时数据已清理")


def verify(application: FastAPI, user_ids: list[int], suffix: str) -> None:
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
    for index in (1, 2):
        username = f"p15_verify_{suffix}_{index}"
        password = token_urlsafe(32)
        payload = {"username": username, "email": f"{username}@example.invalid", "password": password}
        user = call("POST", "/auth/register", 201, json=payload)
        user_ids.append(user["id"])
        assert "password_hash" not in user and "password" not in user
        call("POST", "/auth/register", 409, json=payload)
        call("POST", "/auth/login", 401, json={"identifier": username, "password": token_urlsafe(16)})
        token = call("POST", "/auth/login", json={"identifier": username, "password": password})
        headers.append({"Authorization": f"Bearer {token['access_token']}"})
    owner, other = headers
    call("GET", "/users/me", 401)
    assert call("GET", "/users/me", headers=owner)["id"] == user_ids[0]
    call("GET", "/community/projects", headers=owner)
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
    print("P15 认证、Project、Workflow、Context、Agent、Engine HTTP 链路通过")

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
    report = call("POST", "/learning-reports", 201, headers=owner, json=report_input)
    assert report["status"] == "completed", "报告生成失败，未伪造成功"
    assert report["structured_data"]["total_learning_minutes"] == 60
    assert report["structured_data"]["project_average_progress"] == workspace_project["progress"], \
        "工作台与学习报告的项目进度不一致"
    assert call("GET", f"/learning-reports/{report['id']}", headers=owner)["summary"] == report["summary"]
    call("GET", f"/learning-reports/{report['id']}", 404, headers=other)
    call("POST", "/learning-reports", 409, headers=owner, json=report_input)

    call("POST", project_path + "/publish", headers=owner, json={"tags": [f"p15_{suffix}"]})
    call("POST", project_path + "/view", headers=other)
    for action in ("like", "favorite"):
        first = call("POST", project_path + f"/{action}", headers=other)
        second = call("POST", project_path + f"/{action}", headers=other)
        assert first == second and first["active"]
    comment = call("POST", project_path + "/comments", 201, headers=other,
                   json={"content": "P15 联调样本：实践步骤清晰"})
    call("DELETE", f"/comments/{comment['id']}", 403, headers=owner)
    detail = call("GET", f"/community/projects/{project['id']}", headers=other)
    assert detail["view_count"] == 1 and detail["comment_count"] == 1
    assert detail["liked"] and detail["favorited"]
    call("DELETE", project_path + "/publish", 204, headers=owner)
    call("GET", f"/community/projects/{project['id']}", 404, headers=other)
    call("DELETE", project_path, 204, headers=owner)
    call("GET", workflow_path, 404, headers=owner)
    record = call("GET", "/learning/records", headers=owner)["items"][0]
    assert record["project"] is None
    print("P15 工作台、学习、统计、报告、社区与删除语义 HTTP 链路通过")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-provider", action="store_true", help="使用本地环境配置的真实 Provider，会消耗模型额度")
    args = parser.parse_args()
    if args.real_provider and not get_ai_settings().deepseek_api_key:
        print("未配置 DEEPSEEK_API_KEY；未运行真实模型验收。")
        return 1
    fake_client = AIClient(IntegrationProvider(), total_timeout_seconds=5, max_retries=0,
                           retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
    provider_context = nullcontext() if args.real_provider else patch(
        "app.api.deps.build_ai_client", return_value=fake_client,
    )
    suffix = token_hex(5)
    user_ids: list[int] = []
    try:
        print(f"P15 模式：{'真实 Provider' if args.real_provider else 'Fake Provider + 真实 HTTP/ASGI + MySQL'}")
        with provider_context:
            verify(create_app(), user_ids, suffix)
        return 0
    finally:
        cleanup(user_ids, f"p15_{suffix}")


if __name__ == "__main__":
    raise SystemExit(main())
