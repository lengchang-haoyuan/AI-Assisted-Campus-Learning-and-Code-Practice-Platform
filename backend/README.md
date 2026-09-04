# ScholarHub 后端

## 分层边界

```text
app/api/v1/       Router：HTTP 参数、依赖注入和响应映射
app/schemas/      Pydantic 请求/响应 DTO
app/services/     业务用例和流程编排
app/repositories/ SQLAlchemy 查询和持久化
app/models/       ORM Model 和数据库映射
app/core/         配置、数据库、日志、异常和安全基础能力
app/ai/           AIClient、统一 Provider 接口和供应商 HTTP 适配器
```

依赖方向固定为 `Router → Service → Repository → SQLAlchemy Model → MySQL`。Router 不访问 ORM，Service 不拼接 SQL，ORM Model 不直接作为 API 响应。

当前 health 路由只调用 `HealthService`，不需要访问数据库。后续业务路由通过 `app.api.deps.DatabaseSession` 注入 Session，并把 Session 交给 Repository；依赖结束时 Session 会在 `finally` 中关闭。

## 启动

复制 `.env.example` 为 `.env`，填写数据库连接并生成独立的 JWT Secret。`JWT_SECRET` 最少 32 字符，禁止提交到 Git：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/v1/health`

## 用户认证

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/users/me
```

注册和登录使用 JSON。登录的 `identifier` 可填写用户名或邮箱：

```json
{
  "identifier": "student_01",
  "password": "用户输入的密码"
}
```

密码使用 Argon2id 哈希，JWT 使用环境变量配置的 HS256 和过期分钟数。`/users/me` 要求 `Authorization: Bearer <token>`；缺少、无效或过期 Token 返回 401，已认证但账号不可用返回 403。

## 项目管理

以下接口均要求 Bearer Token，且只允许访问当前用户拥有的项目：

```text
GET    /api/v1/projects?page=1&page_size=20
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
PUT    /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}
```

列表按 `created_at DESC, id DESC` 稳定排序，`page` 范围为 1-10000，`page_size` 范围为 1-100。空列表返回 `items: []`、`total: 0` 和 `total_pages: 0`。`PUT` 支持只提交需要修改的字段，但请求体不能为空；`owner` 和 `owner_id` 不接受客户端输入。

## ProjectContext

ProjectContext 复用 `projects.context_data` JSON 字段，不新增数据库表。以下接口均要求 Bearer Token，并按 Project 所有者隔离：

```text
POST /api/v1/projects/{project_id}/context
GET  /api/v1/projects/{project_id}/context
PUT  /api/v1/projects/{project_id}/context

POST /api/v1/workflows/{workflow_id}/nodes/{node_id}/context/read
POST /api/v1/workflows/{workflow_id}/nodes/{node_id}/context/write
```

- Context 记录 `schema_version`、业务 `version`、UTC 更新时间、更新来源和逐字段元数据。
- 更新请求必须提交 `expected_version`；版本落后返回 409。无实际变化时不增加版本。
- 普通字段整体替换，可空字段使用 `null` 清空；`architecture` 和 `extensions` 使用 JSON Merge Patch 语义，嵌套 `null` 删除对应键。
- Project 核心字段与 Context 更新在同一数据库事务内保持一致。若旧 Project API 直接改变了核心字段，Context 会报告 `is_stale`，节点读取和写入会在同步前返回 409。
- 节点只能使用其类型白名单中的字段；`config.context_reads` 和 `config.context_writes` 只能缩小默认权限，不能扩大权限。
- 字段变化后，直接依赖节点及其 DAG 下游节点会持久化为 `stale`。例如 `language` 从 Python 改为 Java，会使 `project_structure` 和 `prompt` 节点过期。
- Context 拒绝未知顶层字段、过深或过大的 JSON，以及密码、Token、Secret、API Key 和模型原始输入等敏感键。

真实 MySQL 验收脚本会创建隔离的临时数据并在结束时清理：

```powershell
python -m scripts.verify_project_context
```

所有响应包含 `X-Request-ID`。应用错误统一返回：

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "请求的资源不存在",
    "request_id": "..."
  }
}
```

日志使用单行 JSON，`LOG_LEVEL` 默认是 `INFO`；不记录查询字符串、请求体、异常原文或凭据。

## AI Provider

P11 默认使用 DeepSeek 的 OpenAI 兼容 HTTP 接口，调用链为 `Router → AIService → AIClient → DeepSeekProvider`。测试接口要求 Bearer Token：

```text
POST /api/v1/ai/test
```

只在本机未提交的 `.env` 中配置密钥：

```dotenv
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

密钥缺失不会阻止后端和 Swagger 启动；调用测试接口时会返回 `503 ai_configuration_error`，不会伪造模型结果。AI 日志只记录 Provider、模型、状态、耗时、尝试次数和失败类别，不记录密钥、认证头或完整 Prompt。

## 核心 AI Agent

P12 提供项目分析、开发 Prompt 和项目审查三个单回合 Agent。所有接口要求 Bearer Token，运行前校验 Project 所有权和 ProjectContext 新鲜度：

```text
POST /api/v1/agents/project-analysis
POST /api/v1/agents/prompt
POST /api/v1/agents/project-review
GET  /api/v1/agents/results/{request_id}
```

运行接口接收 `project_id` 和对应类型的 `input`。Agent 只读取经过 P10 Schema 校验的 ProjectContext，不执行 shell、SQL、文件或 Workflow；系统规则、Context 和用户输入使用独立消息与数据区块。模型使用单回合、原生 JSON 输出模式，结果仍必须通过对应 Pydantic Schema 才能保存。

`AIRequest` 保存输入哈希、Context 版本、Provider、模型、状态、耗时和 Token 用量，不保存原始输入；`AIResult` 保存通过 Schema 校验的结构化结果。结果查询按当前用户隔离，其他用户使用相同 `request_id` 也无法读取。

Agent 输出上限可通过无秘密环境变量调整，默认值保持在硬上限以内：

```dotenv
AI_AGENT_MAX_TOKENS=3000
AI_AGENT_TEMPERATURE=0.1
```

真实 MySQL 验收脚本使用 Fake Provider 创建隔离数据，验证分析和 Prompt 结果持久化、查询隔离和原始输入不落库，并在结束时清理：

```powershell
python -m scripts.verify_agents
```

## Workflow 执行引擎

P13 在 P09-P12 边界上提供有界的顺序执行链：

```text
Router → WorkflowService → WorkflowEngine → Registry → Agent
       → AIClient → AIProvider → ContextManager → Repository → MySQL
```

运行和查询接口均要求 Bearer Token，并按 Workflow 所属 Project 校验当前用户：

```text
POST /api/v1/workflows/{workflow_id}/run
GET  /api/v1/workflows/{workflow_id}/runs
GET  /api/v1/workflows/{workflow_id}/runs/{run_id}
```

运行请求必须提交当前 `expected_version`。`mode=incomplete` 只执行非成功节点及其下游，`mode=all` 明确重新执行整图。P13 注册 `requirements_analysis`、`tech_stack_analysis`、`architecture_design` 三类节点，执行顺序由 DAG 依赖决定；条件边和未注册节点会被拒绝。

节点结果先经过 Pydantic Schema 校验，再原子保存 `AIResult`、节点输出和 ProjectContext。远程模型调用不处于数据库事务中。技术栈字段改变后，下游架构节点会持久化为 `stale`，当前运行随后重新生成该节点。

运行上限使用无秘密环境变量配置：

```dotenv
WORKFLOW_MAX_NODES=12
WORKFLOW_MAX_ROUNDS=12
WORKFLOW_MAX_COMPLETION_TOKENS=9000
WORKFLOW_TOTAL_TIMEOUT_SECONDS=90
WORKFLOW_RECOVERY_TIMEOUT_SECONDS=120
WORKFLOW_MAX_CONCURRENCY=1
```

当前版本固定顺序执行，只有 AIClient 对明确可重试的短暂且幂等 Provider 失败做有界重试。HTTP 请求取消会取消当前协程并记录 `cancelled`；P13 不提供跨进程取消接口。超过恢复超时的遗留 `running` 记录会在下一次运行时标记失败并恢复对应节点。

Fake Provider + 真实 MySQL 验收脚本会创建隔离临时数据，运行三节点 Workflow，将技术栈由 Python 改为 Java，重新生成下游架构并在结束时清理：

```powershell
python -m scripts.verify_workflow_engine
```

## 数据统计与 AI 学习报告

P14 统计接口均要求 Bearer Token，返回全平台匿名聚合，不返回用户明细。数据库统一使用 UTC，前端通过 `timezone_offset_minutes` 传入当前浏览器相对 UTC 的分钟偏移；趋势范围只允许 7 日或 30 日，缺失日期返回零值而不是伪造活动：

```text
GET /api/v1/statistics/today?timezone_offset_minutes=480
GET /api/v1/statistics/trend?days=7&timezone_offset_minutes=480
GET /api/v1/statistics/projects?days=30&timezone_offset_minutes=480
GET /api/v1/statistics/tech-stacks?limit=10
```

今日访问人数按 `project_views.user_id` 去重；完成任务人数按当日 `daily_tasks.completed_at` 去重；社区互动为浏览、未删除评论、点赞和收藏之和。项目完成时间由 `projects.completed_at` 精确记录，P14 不对已有历史状态回填时间，因此迁移前已完成的项目不会被错误计入历史趋势。

P15 统一项目进度口径：只计算项目所有者的关联任务，按完成率取整数，与工作台一致；没有关联任务时使用 `projects.progress`。统计和新报告均在数据库查询层计算，不回写项目字段或历史报告快照。

学习报告按当前用户隔离，报告周期最多 90 日。Repository 只向 Agent 提供聚合指标，不提供学习记录正文、完整 Prompt 或个人数据；模型结果必须包含 `summary`、`achievement`、`problems`、`suggestions` 和 `structured_data` 并通过 Pydantic 校验：

```text
POST /api/v1/learning-reports
GET  /api/v1/learning-reports?page=1&page_size=20
GET  /api/v1/learning-reports/{report_id}
```

报告生成成功后保存 `AIRequest`、`AIResult` 和 `learning_reports` 关联。Provider 失败或输出无效时，报告持久化为 `failed` 并保存安全失败类别，不伪造完成结果；失败周期可重试，未过期的重复生成返回冲突。

已有数据库先备份并审查增量迁移。脚本检查 P14 新增表、列和索引是否已存在，拒绝部分应用状态；它不能代替完整结构校验。MySQL DDL 不保证整份脚本原子回滚，失败后需人工核对，不能直接重跑或删除已有表。已完整应用时重复运行只报告已应用：

```powershell
python -m scripts.apply_p14_statistics_migration
python -m scripts.verify_database_schema
python -m scripts.verify_statistics_reports
```

## 环境约定

- MySQL 8.0 或更高版本，字符集为 `utf8mb4`，排序规则为 `utf8mb4_0900_ai_ci`。
- 数据库中的 `DATETIME(6)` 统一保存 UTC；Python/API 边界使用带时区的 `datetime`。
- 本地连接信息只写入未提交的 `.env`，不要修改 `.env.example` 保存真实密码。

## 初始化空数据库

先确认目标 MySQL 实例中没有 ScholarHub 业务表，再执行：

```powershell
mysql --user=root --password --execute="source schema.sql"
```

脚本会创建或选择 `scholarhub` 数据库，但不会删除数据库、表或已有数据。遇到同名表时会失败并要求人工检查结构。

## 配置与连接检查

复制 `.env.example` 为 `.env`，仅在本机填写：

```dotenv
DATABASE_URL=mysql+pymysql://用户名:URL编码后的密码@127.0.0.1:3306/scholarhub?charset=utf8mb4
LOG_LEVEL=INFO
JWT_SECRET=至少32字符的随机值
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

然后执行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.check_database
python -m scripts.verify_database_schema
```

## 测试与结构检查

```powershell
python -m unittest discover -s tests -v
```

测试覆盖 health、Swagger、统一异常、错误脱敏、CORS、请求 ID、JSON 日志、Session 释放和 Router 分层边界，同时检查 SQLAlchemy metadata 与 `schema.sql`。`python -m scripts.verify_database_schema` 还会只读对比实际 MySQL 数据库与 Models。

P15 跨模块验收入口如下，Fake 与真实 Provider 模式均已通过；后续失败仍以非零退出码报告：

```powershell
python -X utf8 -m scripts.verify_integration
```

该脚本通过 HTTP/ASGI 请求真实 API 和 MySQL，默认只替换外部 Provider，不依赖开发服务器、不消耗模型额度。它创建随机命名的临时用户和关联数据，在 `finally` 中清理；请使用开发数据库，勿在生产库运行。浏览器演示、真实模型模式和已知边界见 [P15 演示与答辩指南](../开发相关文档/答辩材料/P15演示与答辩指南.md)。
