# ScholarHub

面向高校学生的 AI 辅助学习与代码实践平台。当前已完成 P00-P21 的设计与功能开发，覆盖认证、项目与校园代码社区、学习系统、可视化 Workflow、ProjectContext、AI Provider/Agent、Workflow 执行、真实数据统计、AI 学习报告、校园身份、教学班、教学任务、成果版本、教师反馈和社区人工治理。

项目详情现可进入 AI 工作台，通过页面创建和维护 Context、运行需求分析与开发 Prompt、按请求编号查询和复制结构化结果。Workflow 编辑器提供 Context 新鲜度、AI 运行入口、历史结果、失败续跑和节点结果复制，并支持需求分析、技术栈分析、架构设计以及三个教学节点。社区已改为发布申请、人工审核、举报、下架和复核流程，公开内容读取已审核快照。P22-P24 仍是后续规划；真实教师确认、校方试点批准和真实班级试点均未发生。

## 项目结构

```text
ScholarHub/
├── frontend/   Vue 3 + TypeScript + Vite
├── backend/    FastAPI + Pydantic + SQLAlchemy
└── 开发相关文档/ 规划、提示词、说明、日志、报告、证据与答辩材料
```

项目知识入口：[ScholarHub 知识地图](开发相关文档/知识网络/00-ScholarHub知识地图.md)。在 Obsidian 中将 `开发相关文档` 作为仓库打开，可阅读双向链接笔记并使用内置关系图谱；不需要第三方插件。

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

已有数据库应按顺序备份并执行 `backend/migrations/` 中的增量迁移，不能把 `schema.sql` 当作升级脚本。校园身份不会自动授予：负责人核验现有账号后，首个管理员通过受控命令初始化，后续教师和学生由管理员签发定向邀请。完整命令和权限边界见 [后端说明](backend/README.md#p17-校园身份初始化)。

## 校园身份与教学班

- `/campus/join`：已有账号兑换校园邀请。
- `/campus/admin/accounts`：管理员管理账号元数据、校园资格、邀请和审计。
- `/campus/classes`：教师创建教学班和发布任务，学生查看已加入班级的非草稿任务。
- `/campus/submissions`：学生查看待提交任务和版本历史，教师查看本人班级待评成果。
- `/notifications`：学生查看任务发布与教师反馈通知，并按本人权限进入对应记录。

学生、教师和管理员使用固定校园角色。管理员不能默认读取教学任务正文、私人 Project、Context、学习笔记或 AI 输入；个人 `Course`、`DailyTask`、`Project` 与教学班数据保持分离。

## 校园社区治理

- `/community`：有效校园成员浏览已审核作品或迁移后的“历史待审核”快照，并进行评论、点赞、收藏和有界举报。
- `/projects/:id`：项目所有者填写署名、来源/许可和 AI 辅助声明后申请发布；教师可额外申请实践模板并填写人工审阅说明。
- `/community/governance`：作者查看发布和举报/复核进度；管理员审核作品、处理举报与复核，所有决定要求理由并写入审查记录。
- 私人 Project 修改不会静默替换公开快照；撤回或下架后内容从社区详情和互动入口隐藏，恢复后沿用原审核快照与累计互动数据。

社区入口统一要求有效校园身份。治理页面只返回处理所需的快照、目标摘要和授权字段，不扩大管理员或教师对私人 Project、Context、学习笔记、AI 输入及教学提交的权限。

## AI 工作台与 Workflow

- `/projects/:id/ai`：项目所有者创建、查看和按版本修改 Context，主动同步项目字段，并运行需求分析或开发 Prompt。
- `/workflows/:id`：编辑图、检查已注册节点、查看 Context 过期影响、运行工作流并恢复运行记录和节点结果。
- Context 保存和同步不会自动调用模型；模型调用由用户点击发起。页面离开或浏览器请求中断不表示服务端调用已取消，失败后应先查询已有结果再决定是否重试。
- 前端以纯文本和结构化字段展示模型输出，不直接渲染模型返回的 HTML。教师和管理员身份不会扩大私人 Project、Context 或 AI 结果的读取权限。

## 阶段交付流程

每个阶段独立完成需求、验证、操作日志和完成报告。P00-P15 为原系统交付，P16 为校园试点设计，P17-P21 为已实现功能；P22-P24 只有在前置决策确认后实施。检查通过后创建对应 Git 提交并推送到 `origin/main`，确认远端提交哈希一致后再进入下一节点。

## 当前范围

前端 `/analytics` 使用 ECharts 展示数据库聚合的 7/30 日趋势、项目和技术栈统计，并可生成、刷新后查询当前用户的 AI 学习报告。校园路线验证明细见 [P17 验收报告](开发相关文档/阶段报告/20260905-P17-校园身份与账号管理验收.md)、[P18 验收报告](开发相关文档/阶段报告/20260907-P18-班级与教学任务验收.md)、[P19 验收报告](开发相关文档/阶段报告/20260909-P19-成果提交与教师反馈验收.md)、[P20 验收报告](开发相关文档/阶段报告/20260911-P20-AI功能页面闭环验收.md) 和 [P21 验收报告](开发相关文档/阶段报告/20260911-P21-校园社区治理验收.md)；启动和原系统演示路径见 [P15 演示与答辩指南](开发相关文档/答辩材料/P15演示与答辩指南.md)。依赖安全审计因外部服务超时仍未取得完整结论。
