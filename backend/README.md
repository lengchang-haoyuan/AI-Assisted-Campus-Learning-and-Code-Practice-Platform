# ScholarHub 后端

## 分层边界

```text
app/api/v1/       Router：HTTP 参数、依赖注入和响应映射
app/schemas/      Pydantic 请求/响应 DTO
app/services/     业务用例和流程编排
app/repositories/ SQLAlchemy 查询和持久化
app/models/       ORM Model 和数据库映射
app/core/         配置、数据库、日志、异常和安全基础能力
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
