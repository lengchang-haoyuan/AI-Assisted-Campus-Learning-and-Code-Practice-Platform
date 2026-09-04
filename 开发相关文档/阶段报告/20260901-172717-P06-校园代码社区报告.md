# 任务完成报告：P06 校园代码社区

- 完成时间：2026-09-01 17:27:17 +08:00
- 任务范围：全栈
- 项目根目录：`ScholarHub/`

## 需求摘要

在 P04/P05 Project 能力之上实现项目发布、社区浏览、标签筛选、评论、点赞、收藏和浏览量。复用现有数据库表，只允许登录用户访问；服务端校验项目发布所有权、评论删除所有权和互动幂等性。不实现私信、好友、关注、实时聊天、学习系统、Workflow 或 AI。

## 修改内容

- 新增社区项目列表、详情和已发布标签查询，列表按 `published_at DESC, id DESC` 稳定排序并支持有界分页和标签过滤。
- 新增 owner-only 项目发布与撤下；标签在发布时规范化并写入现有 `tags/project_tags`。
- 新增评论列表、创建和软删除；只有评论作者可删除。
- 新增浏览量原子递增、点赞和收藏的幂等 POST/DELETE，计数始终从数据库读取。
- 新增 `/community`、`/community/projects/:id`，以及个人项目详情中的发布、撤下和社区详情入口。
- 社区页面实现 Loading、空、失败、重试、筛选、分页、危险操作确认、窄屏布局、液态标签、数字滚动和卡片翻面。

## 文件与架构变化

- `backend/app/api/v1/community.py`、`schemas/community.py`、`services/community.py`、`repositories/community.py`：新增社区 Router → Service → Repository 业务切片。
- `backend/app/api/deps.py`、`api/presenters.py`、`api/v1/router.py`：注册依赖、响应映射和路由。
- `backend/app/repositories/project.py`、`schemas/project.py`、`services/project.py`：Project 响应增量提供发布状态、标签和浏览量，保持原 CRUD 契约兼容。
- `backend/tests/test_community.py`：新增 API 与 Service 权限、校验、分页和互动测试。
- `frontend/src/api/community.ts`、`stores/community.ts`、`types/community.ts`：集中社区请求、状态和 DTO。
- `frontend/src/components/CommunityProjectCard.vue`：可访问的社区翻面卡片。
- `frontend/src/views/CommunityView.vue`、`CommunityProjectDetailView.vue`：社区列表、筛选、详情和评论页面。
- `frontend/src/views/ProjectDetailView.vue`：增加项目发布与撤下入口。
- `frontend/src/router/index.ts`、`layouts/AppLayout.vue`、`styles/main.css`：增加社区信息架构与响应式样式。
- 依赖方向保持为页面 → Store/API → Axios；Router → Service → Repository → SQLAlchemy Model → MySQL。

## 关键设计决定

- 决定：保留 `/projects` 作为个人项目管理，新增 `/community` 作为社区浏览边界。
- 原因：避免破坏 P04/P05 owner-scoped CRUD，同时让公开项目查询只返回 `is_published = true` 数据。
- 决定：不修改数据库结构，直接复用 P01 的 `projects/tags/project_tags/comments/likes/favorites`。
- 原因：现有字段、外键、软删除字段与互动唯一约束已满足 P06。
- 决定：重复点赞和收藏采用幂等语义，返回最终 active 状态和数据库计数。
- 原因：支持重复点击和并发唯一约束，不制造重复记录。
- 用户确认：P06 提示词已明确授权新增对应 API 和前端页面；未触发新依赖或数据库变更确认门槛。

## 兼容性与安全影响

- 公共 API：新增社区端点；Project Response 仅增加 `tags/is_published/published_at/view_count`，原字段和路径不变。
- 数据与迁移：未修改 `schema.sql`、SQLAlchemy Models 或迁移历史。
- 权限、秘密和隐私：全部社区接口要求 JWT；发布/撤下校验 Project owner，删除评论校验 Comment user；未记录或提交 Token、密码、Secret 和数据库凭据。

## 验证结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| Python 编译 | `.venv\\Scripts\\python.exe -m compileall -q app tests` | 通过 | 应用与测试可编译 |
| 后端测试 | `.venv\\Scripts\\python.exe -m unittest discover -s tests` | 通过 | 47 项通过，其中 P06 新增 9 项 |
| 后端依赖 | `.venv\\Scripts\\python.exe -m pip check` | 通过 | 无破损依赖 |
| 数据库 | `check_database_connection()` | 通过 | 连接 `scholarhub`，metadata 仍为 18 张表 |
| 前端类型 | `pnpm typecheck` | 通过 | 无 `any` 或关闭类型检查 |
| 前端构建 | `pnpm build` | 通过 | Vite 构建 1696 modules |
| 前端依赖 | `pnpm audit --prod` | 通过 | 无已知生产依赖漏洞 |
| 机械设计检查 | `impeccable detect --json <P06 targets>` | 通过 | 问题列表 `[]` |
| 差异检查 | `git diff --check` | 通过 | 无空白错误 |

## 手工验收

1. 两名临时用户通过真实 FastAPI 与 MySQL 完成创建项目、发布和标签筛选，社区列表返回 1 条匹配数据。
2. 同一用户连续两次点赞和收藏，数据库计数均保持 1。
3. 非评论作者删除返回 403，评论作者删除返回 204；非项目 owner 撤下返回 403。
4. 刷新社区详情后浏览、点赞、收藏和评论计数仍来自数据库；owner 撤下返回 204，随后社区详情返回 404。
5. 浏览器验证桌面和 390×844 移动端、液态标签筛选、卡片翻面、数字滚动、社区详情、评论展示和发布状态入口，控制台无 warning/error。
6. 临时项目、用户与无引用测试标签已清理，残留计数为 0。

## 启动命令

- 后端：`cd backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- 前端：`cd frontend && pnpm dev -- --port 5173`
- 前端 API：通过 `VITE_API_BASE_URL` 配置，示例为 `http://127.0.0.1:8000/api/v1`。

## 未执行或未通过的检查

- 前端没有仓库既有 Lint 或自动化组件测试脚本，因此未虚构通过结果，也未在未确认情况下新增依赖或修改检查策略。
- P05 的 Impeccable HERO 像素门仍为 55% open；该门对应此前参考图，不是 P06 新社区页面的功能失败。P06 detector 已返回空问题列表。

## 剩余风险与后续建议

- 当前浏览量按每次明确调用计数，不做匿名去重；P06 未要求访客指纹或时间窗口去重。
- 标签由项目 owner 在发布时创建；当前没有管理员标签治理，属于后续运营能力而非 P06 范围。
- 建议 Git commit：`feat: implement campus code community`。
