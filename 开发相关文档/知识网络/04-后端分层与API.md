---
tags: [ScholarHub/架构]
updated: '2026-09-07'
---
# 后端分层与 API

FastAPI + Pydantic + SQLAlchemy + MySQL，当前为一个后端应用，不是微服务架构。

`Router → Service → Repository → SQLAlchemy Model → MySQL`

## 各层职责

| 层 | 代码位置 | 责任 |
| --- | --- | --- |
| 入口 | `backend/app/main.py` | 创建应用、挂载路由、中间件和异常处理 |
| Router | `app/api/v1/` | HTTP 输入、认证依赖、调用与响应映射 |
| Schema | `app/schemas/` | 独立请求/响应 DTO，不直接返回 ORM |
| Service | `app/services/` | 所有权、状态变化和业务编排 |
| Repository | `app/repositories/` | SQLAlchemy 查询、聚合及持久化 |
| Model | `app/models/` | 表、字段、约束和关系 |
| 基础设施 | `app/core/`、`app/api/deps.py` | 配置、安全、日志、Session 生命周期和依赖装配 |

AI 专用目录分别见 [[12-ProjectContext上下文]]、[[13-AIProvider]]、[[14-核心Agent]]、[[15-Workflow执行引擎]]。

## API 地图

所有业务路径以 `/api/v1` 开头；Swagger 使用 `/docs`。

- `/health`：健康状态与版本，不证明 MySQL 或模型可用。
- `/auth/*`、`/users/me`：[[06-账号认证与权限]]。
- `/projects/*`、`/community/*`：[[07-项目管理]] 和 [[08-校园代码社区]]。
- `/workspace/*`、`/courses/*`、`/learning/*`：[[09-个人工作台]] 和 [[10-课程计划任务与记录]]。
- `/workflows/*`、`/projects/{id}/context`、`/agents/*`、`/ai/test`：编辑、上下文与 AI 能力。
- `/statistics/*`、`/learning-reports/*`：[[16-统计与AI学习报告]]。
- `/campus/me`、`/campus/invitations*`、`/campus/admin/*`：校园资格、邀请、账号管理和审计，见 [[06-账号认证与权限]]。
- `/campus/classes*`、`/campus/assignments*`：教学班、成员和任务；学生只读取本人班级的非草稿任务。

2026-09-07 生成的 OpenAPI 共 77 个路径，其中 P18 占 9 个路径、14 个操作。

## 错误语义

401 表示未认证或 Token 无效；403 表示已认证但无权；404 是资源不存在；409 是冲突或版本过期；422 是输入不符合 Schema；500 是安全的内部错误。滑块另有 400、429，AI 配置缺失为 503。

错误响应具有 `error.code/message/request_id`；响应包含 `X-Request-ID`。不向客户端回传堆栈、SQL 或内部路径。日志和环境约定见 [[17-启动配置与安全]]。

关联：[[03-前端架构与页面]]、[[05-数据库实体关系]]、[[18-测试证据与答辩]]。
