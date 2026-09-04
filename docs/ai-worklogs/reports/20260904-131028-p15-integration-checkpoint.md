# P15 全系统联调进度报告

> 后续进展：用户已确认修复，完成结果见 [P15 交付报告](20260904-134029-p15-integration.md)。下文保留当时的失败证据与检查点，不代表当前状态。

- 记录时间：2026-09-04 13:10:28 +08:00
- 状态：进行中，修复方案待用户确认；不是完成报告。
- 基线：`main`，P14 提交 `28fd2fa1e45139f77a5c56a44daf664a8bf7f419`。
- 范围：跨模块联调、证据驱动修复和答辩准备；不新增业务功能、依赖或数据库结构。

## 1. 修改和新增文件清单

- 新增 `backend/scripts/verify_integration.py`：HTTP/ASGI + 真实 MySQL 的跨模块验收脚本，默认 Fake Provider，可显式选择真实 Provider。
- 新增 `docs/P15_演示与答辩指南.md`：Windows 启动、演示链路、Swagger 请求、概念与实际代码对应表、口径和简化边界。
- 修改 `README.md`：复制环境示例时不覆盖已有 `.env`，标注 P15 进行中并链接指南。
- 修改 `backend/README.md`：修正技术栈统计请求参数和迁移预检说明，增加集成验收入口。
- 更新 `docs/ai-worklogs/operations.md` 并新增本报告。

应用生产代码尚未修改；公开 API、依赖、数据库结构、已发布迁移和测试策略均未变动。

## 2. 本阶段关键设计和调用链

保留 `Vue → Axios → Router → Service → Repository → SQLAlchemy → MySQL`，AI 经 `Agent → AIClient → Provider` 调用并校验结构化结果。本次脚本仅替换外部模型边界；注册、JWT、权限、业务事务和持久化均使用真实实现。

测试创建两个随机命名用户和关联资源，生成随机密码且不打印，退出时按本次用户 ID 清理。假报告明确标注为确定性测试输出，只用于验证聚合与持久化，不代表真实模型成功。正常真实模式涉及 9 次 Agent/报告调用，本次未执行真实模式。

### 待确认的最小修复

| 问题 | 可达证据 | 推荐方案及影响 |
| --- | --- | --- |
| 报告请求等待不足 | `frontend/src/api/client.ts` 全局 5 秒；`src/api/analytics.ts` 生成报告未覆盖；后端 AI 总超时默认 30 秒。 | 只对报告设置独立有界超时，保留普通 API 的快速反馈；不改 API 或依赖。 |
| 旧账号缓存保留 | `src/stores/auth.ts` 只清空认证；`src/main.ts` 与 `src/layouts/AppLayout.vue` SPA 跳转登录；其他 Store 仍存旧数据。 | 退出或受保护会话失效后完整导航到登录页，清除旧 JavaScript 会话和请求；会改变退出时的页面行为。 |
| 项目进度跨模块不一致 | Workspace 按关联任务计算；Statistics、LearningReport 仓储平均 `Project.progress`。脚本中一个完成任务使工作台为 100%，报告输入仍为 0%。 | 在查询层统一当前项目所有者的关联任务完成率，无任务时沿用项目字段；不改表、不回填已有数据。 |

已向用户说明事实、风险与推荐并询问确认，尚未收到确认。未提前实施这些生产修复。

## 3. 启动命令及必要环境变量

完整命令见 `docs/P15_演示与答辩指南.md`。本次已启动后端 8000、前端 5173；MySQL 使用已有服务。

后端在 `backend` 目录：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

前端在 `frontend` 目录：

```powershell
pnpm dev --port 5173 --strictPort
```

必要配置：`DATABASE_URL`、`JWT_SECRET`、`API_V1_PREFIX`、`CORS_ORIGINS`、`VITE_API_BASE_URL`；真实模型另需 `DEEPSEEK_API_KEY` 和账户可用的模型配置。秘密只在本机忽略文件中，报告未记录其值。Redis 尚未接入，不存在需要启动或降级的 Redis 客户端。

## 4. 执行过的检查和结果

以下 Python 命令均使用 `backend/.venv/Scripts/python.exe`，pnpm 命令在 `frontend` 执行。

| 检查 | 命令 | 实际结果 |
| --- | --- | --- |
| 后端全量测试 | `python -m unittest discover -s tests -q` | 143 项通过，覆盖认证、Project、Community、Learning、Workspace、Workflow、Context、Provider、Agent、Engine、Statistics、Report 及基础架构。 |
| Python 编译 | `python -m compileall -q app scripts tests` | 通过，包含新验收脚本。 |
| 依赖一致性 | `python -m pip check` | 通过；这不是漏洞扫描。 |
| 数据库连接 | `python -m scripts.check_database` | 连接现有开发 MySQL 成功。 |
| SQL/Model/真实结构 | `python -m scripts.verify_database_schema` | 19 表、35 外键及约束/索引结构检查通过。 |
| Context 持久化 | `python -m scripts.verify_project_context` | 版本 1→2→3、节点读写和 stale 检查通过。 |
| Agent 持久化 | `python -m scripts.verify_agents` | Fake Provider 分析/Prompt、查询隔离和敏感输入边界通过。 |
| 引擎真实数据库 | `python -m scripts.verify_workflow_engine` | 三节点运行、技术栈改变与重新生成、5 条节点结果和恢复检查通过。 |
| 统计/报告单模块 | `python -m scripts.verify_statistics_reports` | 聚合、Fake Provider 报告保存和刷新查询通过。 |
| 新增跨模块验收 | `python -X utf8 -m scripts.verify_integration` | 未通过：报告项目平均进度与工作台不一致；临时数据已清理。 |
| 前端类型检查 | `pnpm typecheck` | 通过。 |
| 生产构建 | `pnpm build` | 通过，2344 modules；统计页懒加载 chunk 约 572 KB 有体积提示。 |
| 生产依赖审计 | `pnpm audit --prod` | 失败，npm advisories 请求重试后超时，未取得当前漏洞结论。 |
| 差异空白检查 | `git diff --check` | 通过；Git 提示 Windows 工作区 LF/CRLF 转换，不是代码失败。 |

本仓库没有独立格式化/Lint、Ruff、Mypy 或前端组件/E2E 测试命令。本次没有临时安装工具或关闭检查来报告通过。

## 5. 手工验收步骤和实际结果

已通过真实 HTTP 验证：

- `GET http://127.0.0.1:8000/api/v1/health`：200。
- `GET http://127.0.0.1:8000/docs`：200。
- `GET http://127.0.0.1:5173/login`：200；这只证明页面服务可用，不等同完成浏览器交互验收。
- 未认证访问统计接口：401。
- 从 `http://127.0.0.1:5173` 的 CORS 预检：200 且允许该 Origin。
- 未配置的外部 Origin 预检：400 且不返回 allow-origin。

新增脚本已走过注册/登录、重复注册、错误密码、Project CRUD 权限、分页 422、Context、图保存/恢复/版本与循环 409、分析与 Prompt、三节点运行、Java stale 与重跑、课程/计划/任务、六类学习记录、Dashboard、7/30 日统计和报告保存。执行到报告与工作台进度比较时停止。报告之后的跨用户报告读取、发布、互动和删除链路虽已写入脚本，但尚未在该脚本中走到，不标记通过。

最终浏览器桌面、窄屏、账号切换、慢报告请求与完整链路验收待修复后执行。P10-P13 使用 Swagger 演示；现有前端没有 Context、独立 Agent 和引擎运行的完整操作面板。详细操作见演示指南。

## 6. 失败检查、已知问题和剩余风险

- 三项生产缺口均存在于 P15 基线，并非新增脚本引入；新增脚本使进度差异可重复触发。不能删除一致性断言换取通过。
- 脚本编写期间修正了 Tag 导入位置和工作台查询参数别名；均属于新脚本错误，未改变业务实现。
- 依赖审计网络超时，需要网络恢复后重跑，不能据此声称无漏洞。
- 未进行本阶段真实 Provider 调用或浏览器全链路；以前阶段报告中的成功不能替代 P15 最终验收。
- Redis、管理员角色、Context/Agent/Run 前端面板未实现；引擎顺序执行、无跨进程主动取消，历史完成时间不回填，均已明确记录，不扩展成新增功能。
- 当前没有 release 提交或推送。恢复工作时先确认三项修复方案，再补回归测试、重跑失败链路并完成浏览器和真实模型验证，之后更新完成报告与 Git。

## 7. 建议的 Git commit 信息

最终所有必要验收完成后使用：

```text
release: complete graduation project integration
```

当前保持未提交检查点，不把进行中的 P15 标记为已发布，也不覆盖 P14 提交。确认修复并验收后再按既有规则提交、推送并核对远端哈希。
