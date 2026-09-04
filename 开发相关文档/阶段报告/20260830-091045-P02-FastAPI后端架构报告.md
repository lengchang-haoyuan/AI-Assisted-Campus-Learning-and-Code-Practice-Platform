# 任务完成报告：P02 FastAPI 后端基础架构

- 完成时间：2026-08-30 09:10:45 +08:00
- 任务范围：后端
- 项目根目录：`ScholarHub`

## 需求摘要

基于 P00/P01 建立 `Router → Service → Repository → SQLAlchemy Model → MySQL` 分层边界，提供统一 `/api/v1`、Swagger、异常响应、结构化日志、请求关联 ID、CORS 和数据库 Session 依赖。保持 health 可用，不实现认证或业务功能。

## 修改内容

- 将 health Pydantic DTO、领域状态和业务组装分别放入 Schema、Service 和 Router。
- 新增应用异常类型和统一异常处理，覆盖输入错误、未认证、禁止访问、未找到、冲突、参数校验和内部错误。
- 新增 JSON 日志和请求 ID 中间件，每个响应返回并通过 CORS 暴露 `X-Request-ID`。
- 新增数据库 Session FastAPI 依赖，确保请求结束时在 `finally` 中关闭 Session。
- 建立 `schemas`、`services`、`repositories` 和 `core/security.py` 的职责边界，不提前实现后续业务。
- 增加基础架构自动测试和后端运行文档。

## 文件与架构变化

- `backend/app/main.py`：集中装配 CORS、中间件、异常处理器和版本路由。
- `backend/app/api/deps.py`：Session 与 HealthService 依赖注入。
- `backend/app/api/errors.py`、`middleware.py`：统一错误响应和请求上下文。
- `backend/app/core/exceptions.py`、`logging.py`、`security.py`：异常、日志和后续认证边界。
- `backend/app/schemas/`：API DTO，不依赖 ORM 或 Service。
- `backend/app/services/health.py`：health 用例和领域状态。
- `backend/app/repositories/`：持久化层边界；P02 无业务查询，因此未创建虚构仓储。
- `backend/tests/test_api_foundation.py`：API、异常、CORS、日志、Session 和分层测试。
- 依赖方向：health 为 `Router → HealthService`；后续持久化用例通过 `Service → Repository → Model`，Router 不导入 ORM，Service 不拼 SQL。

## 关键设计决定

- 决定：不新增 `httpx` 或测试框架，使用标准库 `unittest` 和直接 ASGI 调用测试 FastAPI。
- 原因：现有依赖足以覆盖本阶段验收，避免仅为测试客户端增加依赖。
- 用户确认：不需要；没有新增或升级依赖。
- 决定：health 不查询数据库。
- 原因：它是服务存活检查，强制访问 MySQL 会让数据库故障同时隐藏 API 进程状态；数据库连接能力单独通过 Session 依赖验证。
- 用户确认：不需要；health 公共响应保持不变。
- 决定：500 日志只记录异常类型、错误码和请求 ID，不记录异常原文或堆栈。
- 原因：底层异常可能包含 SQL 参数、内部路径或敏感配置。
- 用户确认：不需要；这是日志安全边界且不改变公共 API。

## 兼容性与安全影响

- 公共 API：`GET /api/v1/health` 路径、状态码和响应字段不变；404 等错误改为统一 JSON，并新增 `X-Request-ID` 响应头。
- 数据与迁移：无数据库表、字段、约束、迁移或数据变化。
- 权限、秘密和隐私：未实现认证；错误响应不暴露堆栈、SQL和内部路径，日志不记录请求体、查询字符串、异常原文或凭据。
- CORS：仍只允许环境变量配置的来源和当前 GET 方法，并允许前端读取 `X-Request-ID`。

## 验证结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 后端测试 | `python -m unittest discover -s tests -v` | 通过 | 15 项，包含 7 项 P02 基础架构测试和 8 项 P01 数据库测试 |
| Python 编译 | `python -m compileall -q app scripts tests` | 通过 | 应用、脚本和测试均可编译 |
| 依赖检查 | `python -m pip check` | 通过 | 无损坏或冲突依赖 |
| Health HTTP | `GET /api/v1/health` | 通过 | HTTP 200，响应兼容并包含请求 ID |
| Swagger HTTP | `GET /docs` | 通过 | HTTP 200 |
| 统一错误 | `GET /unknown` | 通过 | HTTP 404，返回稳定错误码、消息和请求 ID |
| CORS | OPTIONS 与带 Origin 的 GET | 通过 | 允许配置来源并暴露 `X-Request-ID` |
| Session DI | 临时 FastAPI 路由注入 `DatabaseSession` | 通过 | 真实连接 MySQL 执行 `SELECT 1`，返回 200 和 `{"value":1}` |
| 分层检查 | Router 源码结构测试 | 通过 | `api/v1` 未导入 SQLAlchemy 或 ORM Models |

## 未执行或未通过的检查

- 未运行 Ruff、Mypy 或 Pyright，因为项目尚未配置这些工具，本阶段没有获批新增检查依赖或修改检查策略。
- 未运行认证、业务 CRUD 或 Repository 查询测试，因为这些能力属于后续节点且本阶段没有对应实现。

## 剩余风险与后续建议

- 当前 `repositories` 只有职责边界，没有业务仓储；P04 实现 Project CRUD 时应按具体查询需求增加，不应提前创建通用 BaseRepository。
- 当前 CORS 只允许 GET，符合现有唯一 API；P03 增加登录接口时需要同步批准并扩展允许的方法。
- P03 应在 `core/security.py` 中接入成熟密码哈希和 JWT 依赖，不应自行实现密码学。

## 建议 Git commit 信息

`feat: establish fastapi layered architecture`
