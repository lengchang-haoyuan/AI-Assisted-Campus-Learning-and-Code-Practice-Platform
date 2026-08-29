# ScholarHub

面向高校学生的 AI 辅助学习与代码实践平台。当前已完成 P00 工程初始化和 P01 数据库设计与建库。

## 项目结构

```text
ScholarHub/
├── frontend/   Vue 3 + TypeScript + Vite
├── backend/    FastAPI + Pydantic + SQLAlchemy
└── docs/       开发操作记录与阶段报告
```

## 环境要求

- Node.js 22+
- pnpm 11+
- Python 3.11+
- MySQL 8.0+

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger：`http://127.0.0.1:8000/docs`

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 启动前端

```powershell
cd frontend
pnpm install
Copy-Item .env.example .env
pnpm dev
```

页面：`http://127.0.0.1:5173`

## 初始化数据库

数据库结构、环境变量和验证命令见 [`backend/README.md`](backend/README.md)。初始化脚本不会删除已有数据库或表：

```powershell
cd backend
mysql --user=root --password --execute="source schema.sql"
```

## 阶段交付流程

每个 P00-P15 节点必须独立完成需求、验证、操作日志和完成报告。检查通过后创建对应 Git 提交并推送到 `origin/main`，确认远端提交哈希一致后再进入下一节点。

## 当前范围

P00 提供前后端工程骨架、CORS、环境配置和健康检查；P01 提供 MySQL `schema.sql`、SQLAlchemy Models、连接检查和结构验证。认证、业务 CRUD、社区接口、Workflow 执行和 AI 调用仍未实现。
