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

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/v1/health`

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
