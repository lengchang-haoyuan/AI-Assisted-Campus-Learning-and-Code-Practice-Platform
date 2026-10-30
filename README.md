# ScholarHub

毕业设计：**基于Spark的校园代码学习平台的学习行为分析及数据可视化**。

学生在平台中管理项目、学习计划和任务，提交代码实践并接收教师反馈与 AI 辅助建议。离线分析通过固定 MySQL 快照、PySpark 清洗关联和 Spark SQL 聚合，生成可追溯的分析批次，再由只读 API 与 ECharts 展示。

## 技术栈与目录

| 部分 | 技术 | 入口 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Element Plus、Vue Flow、ECharts | [frontend](frontend) |
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy、JWT | [backend](backend) |
| 数据存储 | MySQL 8、事务、外键与唯一约束 | [建库脚本](backend/schema.sql)、[增量迁移](backend/migrations) |
| 离线分析 | PySpark、Spark SQL、JSONL、Parquet | [analytics](analytics)、[Spark 作业](analytics/spark_job.py) |
| AI 实践 | Provider 适配、有限回合工作流、实践会话、本人审阅与建议任务 | [实践服务](backend/app/services/practice.py) |

Spark 负责固定快照的离线计算。页面读取已完成批次；刷新页面不会启动 Spark。当前实验运行于 WSL2 的单机 `local[2]` 环境。

## 本地启动

准备 Python 3.11+（本机使用 3.12）、Node.js 22、pnpm 和 MySQL 8。以下为 Windows PowerShell 命令。

在项目根目录准备后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，填写 `DATABASE_URL` 和至少 32 字符的随机 `JWT_SECRET`。使用 AI 功能时再填写 `DEEPSEEK_API_KEY`；配置字段见 [.env.example](backend/.env.example)。

首次在空库初始化后启动 API：

```powershell
mysql --default-character-set=utf8mb4 --user=root --password --execute="source schema.sql"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

已有数据库应先备份并审查增量迁移，避免重复执行建表脚本。

另开一个终端，在项目根目录启动前端：

```powershell
cd frontend
pnpm install --frozen-lockfile
Copy-Item .env.example .env
pnpm dev
```

- 前端：<http://127.0.0.1:5173>
- 接口文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

新环境注册自己的账号。仓库中的受控分析样本用于核对计算，账号、业务数据和模型密钥需在本地配置。离线 Spark 另需 PySpark 与 Java 环境；[作业入口](analytics/spark_job.py)接收输入快照、输出目录和新 job-id。受控发布脚本含数据库与来源限制，使用前应阅读脚本参数和目标校验。

## 验证与答辩材料

在 `backend` 目录执行后端测试：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -q
```

Windows 缺少 IANA 时区数据时，先将 `PYTHONTZPATH` 指向本机已有的 `zoneinfo` 目录。前端在 `frontend` 目录执行 `pnpm typecheck` 和 `pnpm build`。

2026-10-30 提交前验证：后端 433 项测试通过，前端类型检查与生产构建通过。

- [技术栈、测试与答辩演示指南](开发相关文档/答辩材料/ScholarHub-技术栈测试与答辩演示指南.md)
- [下载答辩演示指南 PDF](output/pdf/ScholarHub-技术栈测试与答辩演示指南.pdf)
- [本次 GitHub 提交验证记录](docs/ai-worklogs/reports/20261030-130108-github-submit.md)

完整中文说明文档已迁至本机同级的 `项目开发与说明文档` 文件夹；该目录独立于本源码仓库。
