# ScholarHub

面向高校学生的 AI 辅助学习与代码实践平台。当前已完成 P00-P15 的功能开发与最终联调，覆盖认证、项目与校园代码社区、学习系统、可视化 Workflow、ProjectContext、AI Provider/Agent、Workflow 执行、真实数据统计和 AI 学习报告。

## 项目结构

```text
ScholarHub/
├── frontend/   Vue 3 + TypeScript + Vite
├── backend/    FastAPI + Pydantic + SQLAlchemy
└── 开发相关文档/ 规划、提示词、说明、日志、报告、证据与答辩材料
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
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger：`http://127.0.0.1:8000/docs`

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 启动前端

```powershell
cd frontend
pnpm install
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
pnpm dev
```

页面：`http://127.0.0.1:5173`

登录页已加入主题切换、过渡动画和基础滑块验证。登录前需先完成滑块；后端校验一次性短期凭证，当前仅支持单 worker 开发部署，不替代专业反机器人服务。接口变化见 [后端认证说明](backend/README.md#用户认证)，本次验证见 [登录页面优化报告](开发相关文档/阶段报告/20260904-190621-登录页面与滑块验证报告.md)。

## 初始化数据库

数据库结构、环境变量和验证命令见 [`backend/README.md`](backend/README.md)。初始化脚本不会删除已有数据库或表：

```powershell
cd backend
mysql --user=root --password --execute="source schema.sql"
```

## 阶段交付流程

每个 P00-P15 节点必须独立完成需求、验证、操作日志和完成报告。检查通过后创建对应 Git 提交并推送到 `origin/main`，确认远端提交哈希一致后再进入下一节点。

## 当前范围

前端 `/analytics` 使用 ECharts 展示数据库聚合的 7/30 日趋势、项目和技术栈统计，并可生成、刷新后查询当前用户的 AI 学习报告。P15 已完成三项跨模块修复、Fake/真实 Provider 全链路和关键浏览器回归；依赖安全审计因外部服务超时未取得结论。启动、演示路径和简化边界见 [P15 演示与答辩指南](开发相关文档/答辩材料/P15演示与答辩指南.md)，验证明细见 [P15 交付报告](开发相关文档/阶段报告/20260904-134029-P15-全系统联调交付报告.md)。
