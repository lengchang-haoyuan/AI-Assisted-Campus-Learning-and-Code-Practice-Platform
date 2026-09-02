# 任务完成报告：P14 数据统计与 AI 学习报告

- 完成时间：2026-09-03 00:18:52 +08:00
- 任务范围：后端 / Agent / 前端 / 数据库迁移
- 项目根目录：`ScholarHub/`

## 需求摘要

在 P06-P13 的社区、学习、项目、Workflow 和 AI 记录基础上，使用真实数据库聚合实现今日指标、7/30 日趋势、项目完成趋势、社区活跃趋势和技术栈统计，并在 Vue 前端使用 ECharts 展示。实现 LearningReportAgent，按当前用户聚合学习、任务、项目、Workflow、AI 和社区数据，生成经过 Schema 校验的学习报告并持久化；Provider 或结果校验失败时必须留下可查询、可重试的失败状态。本阶段不写死统计数据，不伪造报告成功，也不进入 P15 全系统答辩优化。

## 修改和新增文件清单

- `backend/app/models/project.py`、`community.py`、`learning.py`、`user.py`：新增项目完成时间、项目访问记录和统计时间索引及关系。
- `backend/schema.sql`：表达与 Models 一致的 P14 完整空库结构。
- `backend/migrations/20260902_p14_statistics.sql`：已有数据库的可审查增量迁移。
- `backend/scripts/apply_p14_statistics_migration.py`：基线/完整/部分应用预检和幂等迁移执行。
- `backend/app/repositories/statistics.py`、`services/statistics.py`、`schemas/statistics.py`、`api/v1/statistics.py`：数据库聚合统计分层实现和 4 组 API。
- `backend/app/agents/learning_report.py`、`learning_report_schemas.py`：LearningReportAgent、聚合输入和结构化输出 Schema。
- `backend/app/repositories/learning_report.py`、`services/learning_report.py`、`schemas/learning_report.py`、`api/v1/learning_reports.py`：报告来源聚合、生成状态、AIRequest/AIResult/报告持久化和当前用户查询。
- `backend/app/api/deps.py`、`api/v1/router.py`、`models/__init__.py`、`agents/__init__.py`：P14 依赖装配、路由和模型导出。
- `backend/app/repositories/community.py`、`services/community.py`、`services/project.py`：真实访问事件写入和项目完成时间状态同步。
- `backend/tests/test_statistics.py`、`test_learning_reports.py`、`test_database_schema.py`：统计、报告、权限、失败、Schema 和结构测试。
- `backend/scripts/verify_statistics_reports.py`：Fake Provider + 真实 MySQL 聚合、报告持久化和自动清理验收。
- `frontend/src/types/analytics.ts`、`api/analytics.ts`、`stores/analytics.ts`：统计与报告 TypeScript 契约、集中请求和 Pinia 状态。
- `frontend/src/components/EChartPanel.vue`、`views/AnalyticsView.vue`：按需 ECharts 组件和 `/analytics` 业务页面。
- `frontend/src/router/index.ts`、`layouts/AppLayout.vue`、`styles/main.css`：受保护路由、导航和桌面/窄屏样式。
- `frontend/package.json`、`pnpm-lock.yaml`：新增固定版本 `echarts@6.1.0`。
- `README.md`、`backend/README.md`、`docs/ai-worklogs/operations.md`：阶段状态、迁移/API 说明和中文操作记录。

## 本阶段关键设计和调用链

- 统计链：`Statistics Router → StatisticsService → StatisticsRepository → SQLAlchemy → MySQL`。所有 SQL 位于 Repository，Service 负责本地日期到 UTC 边界转换及缺失日期补零，Router 只处理认证、参数和响应。
- 今日访问人数按 `project_views.user_id` 去重；完成任务人数按当日完成任务的 `user_id` 去重；社区互动为访问、未删除评论、点赞和收藏之和。统计是全平台匿名聚合，不返回用户身份。
- 趋势只允许 7/30 日，项目统计和技术栈 Top N 均有边界。数据库存 UTC，API 接收浏览器 `timezone_offset_minutes`，MySQL 分组使用同一偏移，避免跨日口径漂移。
- `project_views` 保存每次已认证访问事件；`projects.completed_at` 只在状态进入 completed 时写入，离开时清空。P14 不回填历史完成时间，避免伪造历史趋势。
- 报告链：`LearningReport Router → LearningReportService → LearningReportRepository → LearningReportAgent → AIClient → AIProvider → Pydantic Schema → AIRequest/AIResult/LearningReport → MySQL`。
- Repository 只提供当前用户的聚合指标，不向模型发送学习记录正文或完整个人数据。LearningReportAgent 单回合输出 `summary`、`achievement`、`problems`、`suggestions` 和 `structured_data`，模型输出始终按不可信 JSON 重新校验。
- 生成前先创建 pending 报告和 AIRequest。成功时原子保存 AIResult 并把报告改为 completed；Provider、超时或 Schema 失败时报告改为 failed，保存安全失败类别且允许重试，不伪造正文。
- 前端链：`AnalyticsView → analytics Store → src/api/analytics.ts → Axios → FastAPI`。ECharts 按模块引入并由独立组件管理 ResizeObserver、更新和销毁；页面提供加载、空、失败、重试、7/30 日液态切换、数字滚动和报告历史/详情状态。

## 启动命令及必要环境变量

已有数据库先执行 P14 增量迁移；脚本可重复运行，但检测到部分应用状态会拒绝继续：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.apply_p14_statistics_migration
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
pnpm install
pnpm dev
```

- 前端：`http://127.0.0.1:5173/analytics`
- Swagger：`http://127.0.0.1:8000/docs`
- Health：`http://127.0.0.1:8000/api/v1/health`
- `DATABASE_URL`、`JWT_SECRET` 和真实报告所需的 `DEEPSEEK_API_KEY` 只保存在未提交的 `backend/.env`；P14 没有新增秘密环境变量。

## 兼容性与安全影响

- 数据库：新增 `project_views` 表、`projects.completed_at` 和面向日期聚合的索引。迁移只执行增量 DDL，不删除、重命名或回填已有业务数据；`schema.sql` 和 Models 已保持一致。
- 公共 API：新增 4 条 Statistics 路径和学习报告创建、列表、详情路径；P00-P13 现有响应保持兼容。
- 依赖：用户批准后新增 `echarts@6.1.0`，未新增后端依赖。pnpm 保持既有构建脚本策略，未放宽间接依赖脚本权限。
- 权限：全部 P14 API 要求 JWT。统计只暴露匿名平台聚合；学习报告严格按当前用户创建和查询，不能读取其他用户报告或原始记录。
- 敏感数据：AI Key 不入库；AIRequest 不保存原始报告输入；日志不记录 Authorization、完整 Prompt、模型正文、数据库凭据或学习记录内容。
- 可靠性：报告周期最多 90 日；未过期 pending 报告拒绝重复创建，超过恢复阈值后可重试；失败报告保持 failed，可查询失败类别且不会被当作完成结果。

## 执行过的测试、Lint、类型检查、构建和结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| Python 编译 | `.venv\Scripts\python.exe -m compileall -q app tests scripts` | 通过 | 应用、测试、迁移和验收脚本均可编译 |
| P14 专项测试 | `python -m unittest tests.test_statistics tests.test_learning_reports -v` | 通过 | 10 项，覆盖日期边界、空趋势、统计语义、认证/校验、Fake Provider、非法/敏感输出、失败持久化和用户隔离 |
| 后端全量测试 | `.venv\Scripts\python.exe -m unittest discover -s tests -v` | 通过 | 143 项，无 P00-P13 回归 |
| 依赖完整性 | `.venv\Scripts\python.exe -m pip check` | 通过 | 无破损后端依赖 |
| 数据库迁移 | `python -m scripts.apply_p14_statistics_migration` | 通过 | 首次应用成功；再次执行识别为已应用且不重复修改 |
| 数据库连接与结构 | `python -m scripts.check_database`、`python -m scripts.verify_database_schema` | 通过 | 连接 `scholarhub`；19 张表、35 个外键及主要约束/索引与 Models 一致 |
| P14 MySQL 验收 | `python -m scripts.verify_statistics_reports` | 通过 | 今日、7 日趋势、项目完成、技术栈和报告刷新持久化一致，临时数据自动清理 |
| 前端类型检查 | `pnpm typecheck` | 通过 | `vue-tsc -b` 无类型错误和 `any` 逃逸 |
| 前端生产构建 | `pnpm build` | 通过 | Vite 8.2.2，2344 modules；统计页按路由懒加载 |
| 前端生产依赖审计 | `pnpm audit --prod` | 通过 | 未发现已知漏洞 |
| OpenAPI 与启动 | 实际 `/openapi.json`、`/docs`、health | 通过 | 54 条路径；6 条 P14 路径存在，Swagger 200，health 为 `ok/0.1.0` |
| 桌面浏览器 | 真实 API + ECharts + DeepSeek | 通过 | 7/30 日、图表、报告生成和刷新后读取成功；无新增运行时 warning/error |
| 390×844 浏览器 | 无界面 Edge + 真实 API | 通过 | 文档/视口均 390px，主导航自身滚动，页面无横向溢出或文字重叠 |
| Impeccable 检测 | 单次 `detect.mjs --json` | P14 通过 | 只报告 P09 既有 Workflow 画布网格/侧标和 P05 HERO 门，不修改本阶段无关设计 |

## 手工验收步骤和实际结果

1. 应用增量迁移并再次运行迁移脚本，确认首次建立 `project_views`、`completed_at` 和索引，重复执行只报告已应用。
2. 使用临时用户创建并发布一个完成状态项目，完成一项任务、保存 90 分钟学习记录，并产生访问、评论、点赞和收藏事件。
3. 打开 `/analytics`，确认今日访问人数 1、完成任务人数 1、平台项目 1、已发布项目 1、社区互动 4、已完成项目 1；这些值与 MySQL 来源一致。
4. 在页面切换近 7 日和近 30 日，日期范围分别为 7/30 个本地自然日，缺失日期展示零；ECharts 无障碍树包含系列和数据说明。
5. 调用真实 DeepSeek 生成一份学习报告，报告状态为 completed，摘要、成果、问题、建议和结构化指标均通过 Schema；离开页面再返回后仍从 MySQL 读取同一报告。
6. Fake Provider 测试无效 JSON、敏感输出和 Provider 失败，确认报告保持 failed、没有伪造正文，并允许按定义重试。
7. 在 390×844 下打开真实统计页，确认文档无横向溢出，7 个主导航入口可在导航条内横向滚动，指标卡、图表和报告区域响应式排列。
8. 按精确用户名清理浏览器验收数据，删除 2 个临时用户及其报告、AI、项目、社区和学习记录；清理后残留用户为 0。

## 未执行或失败的检查、已知问题和剩余风险

- Ruff、Mypy、Pytest 未运行：仓库没有声明这些配置或依赖，后端标准检查仍为 `unittest`；未为 P14 擅自改变检查策略。
- 前端没有 ESLint、组件测试或正式 E2E 脚本，无法运行对应检查；已用 `vue-tsc`、生产构建、依赖审计和真实桌面/移动浏览器路径补足当前证据。
- `AnalyticsView` 生产 chunk 约 571.89 KB、gzip 194.09 KB，Vite 给出 500 KB 提示。该路由已懒加载，不增加首页主包；后续性能优化可再拆 ECharts 图表模块，但 P14 不为警告引入新的构建策略。
- Impeccable 单次检测命中 `main.css` 中 P09 Workflow 画布的网格背景和节点侧边标识，以及 P05 参考图 HERO 门仍 open；这些不是 P14 新增页面问题，按阶段范围未修改。
- P14 不回填迁移前已完成项目的 `completed_at`，所以历史项目完成趋势从迁移后开始精确。若 P15 需要导入历史，应基于可证明来源的审计数据单独设计迁移，不能按当前状态反推完成日期。

## 建议的 Git commit 信息

`feat: implement statistics and ai learning reports`
