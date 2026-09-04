# 任务完成报告：P07 个人工作台

- 完成时间：2026-09-01 17:51:50 +08:00
- 任务范围：全栈
- 项目根目录：`ScholarHub/`

## 需求摘要

在认证、Project CRUD 和社区能力基础上实现当前登录用户的个人工作台。Dashboard 必须使用真实 API 聚合今日任务、最近项目、学习进度、项目进度和最近学习记录；任务支持创建、查看、完成和关联项目，学习记录保存内容、类型、时长和关联项目。只使用确定性业务逻辑，不实现 P08 学习计划、AI、Workflow 或学习报告。

## 修改内容

- 新增工作台 Dashboard、任务列表/创建/完成、项目进度列表/详情、学习记录列表/创建 API。
- Dashboard 按前端传入的本地日期和 UTC 偏移计算当日记录区间，任务完成率与学习分钟均由 MySQL 聚合。
- 项目进度优先由关联任务完成比例计算；无关联任务时回退到 Project 已有 `progress` 字段。
- 任务完成采用幂等语义；任务和记录关联项目时由 Service 校验当前用户所有权。
- 新增五个工作台页面、二级导航、任务表单、学习记录表单和 Pinia Store，完整处理 Loading、空、失败、重试、重复提交与完成后的状态刷新。
- 沿用现有轻松色系，使用液态分段筛选、数字滚动和动画进度条；桌面与窄屏均保持可读。

## 文件与架构变化

- `backend/app/api/v1/workspace.py`、`schemas/workspace.py`、`services/workspace.py`、`repositories/workspace.py`：新增 Router → Service → Repository 工作台切片。
- `backend/app/api/deps.py`、`api/presenters.py`、`api/v1/router.py`：注册依赖、显式 Response Schema 映射和路由。
- `backend/app/schemas/project.py`、`services/project.py`：Project 响应增量公开已有 `progress`，不改变持久化结构。
- `backend/tests/test_workspace.py`：新增 API 与 Service 的认证、所有权、幂等、聚合、分页和校验测试。
- `frontend/src/types/workspace.ts`、`api/workspace.ts`、`stores/workspace.ts`：集中定义 DTO、Axios 请求和跨页面状态一致性。
- `frontend/src/components/WorkspaceNav.vue`、`TaskForm.vue`、`LearningRecordForm.vue`：新增工作台导航和可复用表单。
- `frontend/src/views/WorkspaceDashboardView.vue`、`WorkspaceTasksView.vue`、`WorkspaceProjectsView.vue`、`WorkspaceProjectDetailView.vue`、`WorkspaceRecordsView.vue`：实现 P07 全部页面。
- `frontend/src/domain/workspace.ts`、`router/index.ts`、`styles/main.css`、`types/project.ts`：增加展示映射、路由、响应式样式和 Project progress 类型。

## 关键设计决定

- 决定：不修改 P01 数据库结构，复用 `daily_tasks`、`learning_records` 和 `projects.progress`。
- 原因：现有字段已覆盖 P07，避免在 P08 前产生结构漂移。
- 决定：Dashboard 学习进度定义为所选日期任务完成率。
- 原因：P07 禁止 AI 计划和报告，任务完成率是确定、可审查且可重复计算的指标。
- 决定：项目存在关联任务时以完成任务比例作为进度，无关联任务时使用持久化进度。
- 原因：让 P07 任务形成真实反馈，同时保持 P04 已有 Project 数据兼容。
- 决定：前端传递本地日期和 UTC 偏移，后端转换为 UTC 半开区间查询学习记录。
- 原因：数据库时间保持 UTC，页面按用户本地日历日展示。
- 用户确认：P07 提示词授权新增对应 API 与页面；本阶段没有触发新增依赖或数据库变更确认门槛。

## 兼容性与安全影响

- 公共 API：仅新增 `/api/v1/workspace/*`；Project Response 增加已有 `progress` 字段，原路径与字段保持兼容。
- 数据与迁移：未修改 `schema.sql`、SQLAlchemy Models、18 张既有表或迁移历史。
- 权限：所有工作台端点要求 JWT；任务、记录和项目查询按 current user 隔离，关联项目与任务完成执行服务端 owner 校验。
- 秘密和隐私：未写入或输出数据库密码、JWT Secret、完整 Token、认证头或内部堆栈。

## 验证结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| Python 编译 | `.venv\\Scripts\\python.exe -m compileall app` | 通过 | 应用模块可导入 |
| 后端测试 | `.venv\\Scripts\\python.exe -m unittest discover -s tests -q` | 通过 | 54 项通过，其中 P07 新增 7 项 |
| 后端依赖 | `.venv\\Scripts\\python.exe -m pip check` | 通过 | 无破损依赖 |
| 数据库连接 | `.venv\\Scripts\\python.exe -m scripts.check_database` | 通过 | 连接数据库 `scholarhub` |
| 前端类型 | `pnpm typecheck` | 通过 | 严格 TypeScript，无 `any` 或关闭检查 |
| 前端构建 | `pnpm build` | 通过 | Vite 构建 1712 modules |
| 前端依赖 | `pnpm audit --prod` | 通过 | 无已知生产依赖漏洞 |
| 机械设计检查 | `node .../impeccable/scripts/detect.mjs --json frontend/src` | 已处理 | 单次检测 3 个顶部强调线问题，已移除；按协议不重复检测 |
| 差异检查 | `git diff --check` | 通过 | 无空白错误，仅显示既有换行转换提示 |

## 手工验收

1. 临时用户通过真实 FastAPI 与 MySQL 创建项目、任务和学习记录，Dashboard 初始任务进度为 0%、当日学习记录为 45 分钟。
2. 完成任务后 Dashboard 进度更新为 100%，重复完成保持同一 `completed_at`，验证幂等语义。
3. 项目详情返回 1 项关联任务、1 条记录和 100% 项目进度；刷新后数据仍来自 MySQL。
4. 浏览器实际创建第二项任务并完成，保存第二条学习记录；任务页和记录页均从 API 刷新，控制台无 warning/error。
5. 浏览器验证 1440×900 桌面总览，以及 390px 总览、任务、项目详情；无横向溢出、文本遮挡或状态错位。
6. 临时用户、项目、2 项任务和 2 条学习记录按外键依赖顺序清理，四类残留计数均为 0。
7. `/docs` OpenAPI 可见 6 个工作台路径，`/api/v1/health` 返回 `status=ok` 与版本 `0.1.0`。

## 启动命令

- 后端：`cd backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- 前端：`cd frontend && pnpm dev`
- 前端 API：通过 `VITE_API_BASE_URL` 配置，示例为 `http://127.0.0.1:8000/api/v1`。
- 必要环境变量：沿用 `.env.example` 中的 `DATABASE_URL`、`JWT_SECRET`、`CORS_ORIGINS` 和 `VITE_API_BASE_URL`，真实值不进入版本库。

## 未执行或未通过的检查

- 前端没有仓库既有 Lint 或自动化组件测试脚本，未在未确认情况下新增依赖或修改检查策略。
- 数据库检查脚本直接按文件执行会因导入路径缺少项目根目录失败；按 README 既有模块入口 `python -m scripts.check_database` 执行通过，不需要改代码。
- Impeccable 检测按协议只运行一次；发现的 3 个机械问题已按输出移除，未执行第二次检测。
- P05 的 Impeccable HERO 像素门仍为 55% open；该门对应此前参考图，不是 P07 功能或响应式验收失败。

## 剩余风险与后续建议

- P07 仅实现任务和学习记录的创建、查看与任务完成，没有编辑、删除或 P08 学习计划语义，符合本阶段边界。
- Dashboard 的“今日”依赖浏览器提供日期与 UTC 偏移；服务端已限制偏移范围，但尚未引入用户个人时区配置。
- 建议 Git commit：`feat: implement personal workspace`。
