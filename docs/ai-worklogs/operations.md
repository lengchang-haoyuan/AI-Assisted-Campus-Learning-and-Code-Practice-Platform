# AI 操作日志

## 2026-08-29 21:51:53 +08:00

- 操作：阅读 `README_使用顺序.md`、`P00` 到 `P15` 规划文档，以及前后端目录职责文档
- 目标：理解从零开始建设 ScholarHub 所需的阶段顺序、技术栈、模块边界和验收要求
- 原因：为每个阶段生成可直接投喂给代码 AI 的提示词
- 结果：完成规划梳理；确认当前 ScholarHub 目录暂无业务代码和 Git 历史
- 恢复方式：本次仅新增文档，不涉及代码、数据库或外部系统状态

## 2026-08-29 21:52:00 +08:00

- 操作：新增 `开发相关文档/AI提示词/README.md` 及 `P00` 到 `P15` 提示词文件
- 目标：把规划转换为可逐阶段执行的独立开发任务
- 原因：用户要求从零开始按规划向 AI 投喂提示词
- 结果：完成；共 17 个提示词使用说明和阶段文件，编号连续
- 恢复方式：删除本次新增的提示词目录和文件即可；未修改原规划文档

## 2026-08-29 21:52:30 +08:00

- 操作：执行文件数量、编号连续性、关键术语和标题检查
- 目标：确认提示词文件完整且覆盖项目关键链路
- 原因：文档交付前校验
- 结果：通过；P00-P15 全部存在，关键技术和验收内容已覆盖
- 恢复方式：本次为只读检查，无需恢复

## 2026-08-29 22:16:33 +08:00

- 操作：完成 P00 前后端工程初始化、依赖安装和真实联调
- 目标：`frontend/`、`backend/`、根目录 README 与忽略规则
- 原因：建立 Vue 3 + TypeScript + Vite 与 FastAPI + Pydantic + SQLAlchemy 的最小可运行骨架
- 结果：完成；health、Swagger、CORS、前端加载/成功/失败/恢复状态、移动端布局、类型检查和生产构建均验证通过
- 恢复方式：本阶段只新增工程骨架；删除本次新增的 `frontend/`、`backend/`、根目录 `README.md` 和 `.gitignore` 对应内容即可恢复，未修改数据库或外部系统
- 验证：`pnpm typecheck`、`pnpm build`、Python `compileall`、`pip check`、HTTP health/docs/404/CORS、浏览器桌面与 390×844 视口检查
- 备注：TypeScript 最新 7.0.2 与当前 vue-tsc 不兼容，经确认固定为 5.9.3；当前目录不是 Git 仓库，未执行提交

## 2026-08-29 22:20:45 +08:00

- 操作：依据 `frontend-backend-code-standards` Skill 审查 P00 工程
- 目标：前端、后端、配置、依赖、验证记录和完成报告
- 原因：确认 P00 是否按用户编写的代码规范执行
- 结果：整体符合但不是完全符合；发现 `.env` 加载说明不一致、后端依赖未锁定、前端错误提示固定端口三个问题
- 恢复方式：本次仅新增审查记录和报告，未修改业务代码、依赖或运行配置
- 验证：重新执行 `pnpm typecheck`、`pnpm build`、Python `compileall`、`pip check` 和 health 请求，均通过

## 2026-08-29 22:45:26 +08:00

- 操作：完成 P01 MySQL 数据库设计、非破坏性建库脚本和 SQLAlchemy Models
- 目标：建立用户、项目、社区、课程学习、Workflow 和 AI 记录共 17 个核心实体及项目标签关联表
- 原因：为后续认证、CRUD、Workflow 和 AI 阶段建立统一持久化契约，本阶段不实现业务 API
- 结果：完成；`schema.sql` 已在本机空 MySQL 8.0 实例执行，建立 18 张表，实际数据库的 33 个外键、约束和索引与 Models 一致
- 恢复方式：源码可删除本次新增数据库文件并还原配置变更；数据库当前仅含空表，如需移除必须先人工确认后执行，不在本次任务中自动删除
- 验证：8 项 `unittest` 通过，Python `compileall` 和 `pip check` 通过，环境变量 SQLAlchemy 连接通过，实际库只读结构对照通过，P00 health 与 Swagger 回归通过
- 安全：数据库凭据仅通过交互式输入用于本次验证，未写入源码、`.env`、命令行参数、日志或报告；AI 请求表不保存 API Key、原始提示词或原始敏感输入
- 备注：新增依赖 `PyMySQL` 与 `pydantic-settings` 已在执行前说明事实、风险和推荐方案并经用户批准；当前目录不是 Git 仓库，未执行提交

## 2026-08-29 23:07:44 +08:00

- 操作：初始化 Git 仓库、建立 `origin`、提交 P00-P01 基线并推送 GitHub
- 目标：`https://github.com/lengchang-haoyuan/AI-Assisted-Campus-Learning-and-Code-Practice-Platform.git`
- 原因：用户要求发布当前项目，并要求以后每个节点验收后提交和推送
- 结果：完成；创建 `main`，基线提交为 `7cf42228e90cd403bc9d5d998034e1274683bd69`，本地与远端 `refs/heads/main` 哈希一致
- 恢复方式：本次不删除远端仓库或重写历史；如需撤销代码，应通过新的 revert 提交处理
- 验证：后端 8 项结构测试、Python 编译、`pip check`、前端类型检查和生产构建均通过；远端哈希通过 `git ls-remote` 核对
- 安全：暂存预览确认 `.env`、`.venv`、`node_modules`、构建产物和本地依赖缓存未进入提交，未提交真实数据库凭据
- 备注：根 README 和使用顺序已明确“每节点验证、更新报告、提交、推送并核对远端哈希”的交付流程

## 2026-08-30 09:10:45 +08:00

- 操作：完成 P02 FastAPI 后端分层基础架构
- 目标：建立 Router、Schema、Service、Repository、Model 的职责边界，并提供统一异常、结构化日志、请求 ID、CORS 和数据库 Session 依赖
- 原因：为后续认证和业务接口提供稳定基础，不在本阶段实现任何业务功能
- 结果：完成；health 响应保持兼容，未知路由及应用异常使用统一错误结构，Session 可通过 FastAPI 依赖获取并可靠关闭
- 恢复方式：回退本阶段提交即可；本次未修改数据库结构、数据或外部服务配置
- 验证：15 项 `unittest`、Python `compileall`、`pip check`、真实 HTTP health/Swagger/404/CORS、真实 MySQL Session 依赖 `SELECT 1` 均通过
- 安全：500 响应和结构化日志不记录异常原文、SQL、请求体、查询字符串或凭据；数据库密码仅交互用于验证，未持久化
- 备注：未新增第三方依赖；未实现注册登录、JWT、Project CRUD、社区、学习、Workflow 执行或 AI Provider

## 2026-08-30 09:25:39 +08:00

- 操作：完成 P03 用户注册、登录、JWT 和当前用户认证闭环
- 目标：实现 `POST /api/v1/auth/register`、`POST /api/v1/auth/login`、`GET /api/v1/users/me`，以及前端 Bearer Token 注入和 401 清理
- 原因：在 P02 分层基础上建立唯一的认证范围，不实现其他业务
- 结果：完成；真实 MySQL 验收得到注册 201、重复注册 409、错误密码 401、登录 bearer Token、当前用户 200、无效 Token 401
- 恢复方式：回退本阶段提交并移除新增依赖；本次未修改数据库结构，验收用户已删除
- 验证：24 项后端测试、Python `compileall`、`pip check`、前端类型检查和生产构建通过；真实数据库确认密码为 Argon2id 哈希且不等于明文
- 安全：JWT Secret 和数据库凭据仅通过环境变量或交互式输入使用，未写入代码、日志或报告；日志不记录密码、Token 和完整认证头
- 依赖确认：用户明确批准新增 `pwdlib[argon2]` 和 `PyJWT`；实际安装 `pwdlib 0.3.1`、`argon2-cffi 25.1.0`、`PyJWT 2.13.0`，未安装不需要的 `python-multipart`
- 备注：前端 Token 保存在 `sessionStorage`，收到 401 时同时清除存储和 Pinia 当前用户状态；未实现登录页面或业务路由

## 2026-08-30 09:39:12 +08:00

- 操作：完成 P04 Project REST CRUD、所有权校验、有界分页和稳定排序
- 目标：实现 `GET/POST /api/v1/projects` 与 `GET/PUT/DELETE /api/v1/projects/{id}`，所有接口仅允许当前登录用户访问其项目
- 原因：在 P03 认证闭环上建立第一个数据库持久化业务模块，不提前实现社区、Workflow、AI 或前端页面
- 结果：完成；真实 HTTP + MySQL 验证创建 201、跨用户访问/更新/删除 403、更新持久化、删除 204、删除后 404 和空列表语义
- 恢复方式：回退本阶段提交；本次没有修改数据库结构，验收项目和 2 名临时用户均已删除
- 验证：38 项后端测试和 OpenAPI 契约检查通过；Python 编译、依赖检查、前端回归检查和生产构建见单次完成报告
- 安全：owner 只来自 JWT 当前用户，客户端 owner 伪造返回 422；Service 对详情、更新和删除统一执行所有权检查
- 依赖与数据：未新增依赖、未修改 `schema.sql` 或 SQLAlchemy Models；本机 `mysql` CLI 不在 `PATH`，验收清理改用项目已有 SQLAlchemy/PyMySQL 并确认无测试用户残留

## 2026-09-01 12:26:09 +08:00

- 操作：完成 P05 Vue 前端基础框架、认证页面、登录后布局、Project CRUD 页面、个人工作台和个人资料页
- 目标：实现 `/login`、`/register`、`/`、`/projects`、`/projects/:id`、`/workspace/dashboard`、`/profile`，并通过真实 FastAPI API 完成首条业务闭环
- 原因：在 P03/P04 认证和 Project API 基础上建立可运行的前端业务入口，不提前实现 P06 社区、P07 学习数据或 P09 Workflow
- 结果：完成；Router、Pinia、Axios Token 注入和 401 清理、认证状态、项目列表/创建/详情/编辑/删除确认、Loading/空/失败/重试状态均已实现
- 恢复方式：回退本阶段提交；本次未修改公共 API、数据库结构或依赖，临时验收项目和账号已清理
- 验证：前端类型检查与生产构建通过；后端 38 项测试、Python 编译、`pip check`、MySQL 连接和结构检查通过；浏览器真实验证全部 P05 路由、CRUD、390×844 响应式、液态筛选、数字滚动、卡片翻面和失败重试，控制台无错误
- 设计：采用“轻盈实验室布告板”基调并记录 `DESIGN.md`；最终设计检测器无问题。严格 HERO 像素门为 55% 且保持 open，因为参考图包含 P06/P07/P09 后续数据，当前阶段未用虚构数据换取像素一致
- 安全：Token 保存在 `sessionStorage`，前端路由守卫仅改善导航体验，所有资源权限仍由后端 JWT 与 owner 校验；未提交数据库凭据、JWT Secret、测试密码或 Token

## 2026-09-01 17:27:17 +08:00

- 操作：完成 P06 校园代码社区、项目发布、标签筛选、评论、点赞、收藏和浏览量闭环
- 目标：在现有 Project 与社区表结构上实现真实 API、前端社区列表与详情、个人项目发布入口及互动状态
- 原因：按 P06 范围连接校园代码社区与个人项目库，不进入私信、关注、实时聊天、学习系统或 AI 能力
- 结果：完成；新增 `/api/v1/community/*` 浏览接口及项目评论、点赞、收藏、浏览、发布/撤下接口，前端新增 `/community` 和 `/community/projects/:id`
- 恢复方式：回退本阶段提交；本次未新增依赖、未修改 `schema.sql` 或 SQLAlchemy Models，临时验收用户、项目和孤立标签已清理
- 验证：后端 47 项测试、Python 编译、`pip check`、MySQL 连接通过；前端类型检查、生产构建和生产依赖审计通过；真实 MySQL 两用户联调覆盖 403/404/204、重复互动幂等和刷新持久化
- 设计：桌面与 390×844 窄屏、液态标签筛选、数字滚动、卡片翻面、社区详情与评论状态通过浏览器检查，控制台无 warning/error，Impeccable detector 返回空问题列表
- 安全：所有社区接口要求 JWT；发布/撤下校验项目 owner，评论删除校验评论作者；响应不返回 ORM、认证头、Token、数据库凭据或内部异常
- 已知限制：P05 参考图 HERO 门仍为 55% open，属于此前包含 P06/P07/P09 未来内容的像素复刻任务；P06 新页面按现有 `DESIGN.md` 扩展，未为像素分数伪造后续业务数据

## 2026-09-01 17:51:50 +08:00

- 操作：完成 P07 个人工作台、任务管理、项目进度和学习记录闭环
- 目标：实现 `/workspace/dashboard`、`/workspace/tasks`、`/workspace/projects`、`/workspace/projects/:id`、`/workspace/records` 及对应真实 API
- 原因：在 P03/P04/P06 基础上为当前用户聚合任务、项目与学习记录，不进入 P08 学习计划、AI、Workflow 或报告能力
- 结果：完成；Dashboard 由数据库聚合今日任务、学习分钟、任务完成率和项目统计，任务支持创建/完成/关联项目，学习记录支持内容、类型、时长和项目关联
- 恢复方式：回退本阶段提交；本次未新增依赖、未修改 `schema.sql`、SQLAlchemy Models 或迁移，浏览器验收数据已按外键依赖顺序清理
- 验证：后端 54 项测试、Python 编译、`pip check`、MySQL 连接通过；前端类型检查、1712 modules 生产构建和生产依赖审计通过；真实 MySQL 与浏览器完成任务和记录闭环
- 设计：沿用轻盈实验室布告板基调，使用液态任务筛选、数字滚动和动画进度；桌面与 390px 窄屏无横向溢出，控制台无 warning/error
- 安全：任务、记录和工作台项目全部按 JWT 当前用户隔离，Service 校验关联项目和任务所有权；未提交数据库凭据、测试密码、Token 或内部异常
- 已知限制：Impeccable 单次检测发现的 3 个统计卡顶部强调线已移除；按检测协议未重复运行。P05 HERO 门仍为 55% open，与 P07 功能验收无关

## 2026-09-01 22:35:17 +08:00

- 操作：完成 P08 课程、学习计划、每日任务和学习记录完整业务闭环
- 目标：新增 `/api/v1/courses`、`/api/v1/learning/*` 分层 API，以及 `/learning`、`/learning/tasks`、`/learning/records` 前端页面
- 原因：在 P07 个人工作台基础上建立确定性的学习系统，为后续统计和报告保留真实结构化数据，不接入 AI
- 结果：完成；课程、计划、任务和记录均支持完整读写，任务完成与计划进度在同一事务中保持一致，P07 旧完成入口同步兼容计划进度
- 恢复方式：回退本阶段提交；本次未新增依赖、未修改 `schema.sql`、SQLAlchemy Models 或迁移，临时验收数据已清理
- 验证：后端 62 项测试、Python 编译、`pip check`、MySQL 连接通过；前端类型检查、1730 modules 生产构建和生产依赖审计通过；真实 HTTP + MySQL 验收计划进度达到 100%
- 设计：沿用轻盈实验室布告板基调，新增液态学习导航、数字滚动和 transform 进度动画；桌面与 390px 窄屏无横向溢出，控制台无错误
- 安全：全部资源按 JWT 当前用户隔离，Service 校验 plan/project/course/task 所有权；未提交数据库凭据、JWT Secret、测试密码、Token 或内部异常
- 已知限制：仓库仍无前端 Lint 和组件测试脚本；P05 HERO 门属于既有参考图验收项，与 P08 功能无关

## 2026-09-01 23:24:42 +08:00

- 操作：完成 P09 Workflow 持久化分层 API 与 Vue Flow 可视化编辑器
- 目标：实现 Workflow、Node、Edge CRUD、整图原子保存、图合法性校验，以及 `/workflows` 和 `/workflows/:id` 前端闭环
- 原因：在认证和 Project 所有权基础上建立可保存、可恢复的可视化开发流程，本阶段不接 AI、不执行 Agent
- 结果：完成；两个节点可添加、配置、拖拽和连线，保存后版本递增，刷新恢复位置、配置和边，过期版本与循环图均返回 409 且不污染原图
- 恢复方式：回退本阶段提交并移除 `@vue-flow/core`；本次未修改数据库结构、Models 或迁移，临时验收账号、项目和工作流已清理
- 验证：后端 72 项全量测试和 10 项 Workflow 专项测试通过；Python 编译、`pip check`、MySQL 连接、OpenAPI、前端类型检查、1752 modules 生产构建、生产依赖审计和真实浏览器桌面/390px 验收通过
- 设计：沿用轻盈实验室布告板基调，提供节点库、画布、缩放、节点配置和图检查；空图保持稳定缩放，已有图在布局稳定后自动适配，窄屏无页面横向溢出
- 安全：Workflow 所属 Project 和当前用户权限由 Service 校验，整图保存使用版本复查和事务，未记录密码、Token、数据库凭据或内部异常
- 依赖确认：用户明确批准 `@vue-flow/core@1.48.2`；pnpm 忽略间接 `vue-demi` 构建脚本，但直接 import、类型检查和生产构建均通过，未放宽脚本策略
- 已知限制：仓库仍无前端 Lint、组件测试和 E2E 脚本；P05 HERO 门属于既有参考图验收项，与 P09 功能无关

## 2026-09-02 12:46:24 +08:00

- 操作：完成 P10 ProjectContext 领域模型、持久化分层 API、节点权限与下游失效规则
- 目标：让 Project 和 P09 Workflow 共享可版本化上下文，支持创建、读取、修改、保存、节点受限读写和 stale 识别
- 原因：为 P11/P12 Agent 提供经过 Schema 校验且按项目所有权隔离的确定性上下文，本阶段不接 AI Provider 或执行 Workflow
- 结果：完成；复用 `projects.context_data`、`workflow_nodes.context_version/status`，新增 ContextBuilder、ContextManager、Repository、Service、Schema、Router 和 MySQL 验收脚本，未修改数据库结构或依赖
- 恢复方式：回退本阶段提交；`schema.sql` 和 18 张现有表无需回滚，真实 MySQL 验收临时用户、项目和 Workflow 已自动清理
- 验证：Python 编译、88 项后端测试、16 项 P10 专项测试、`pip check`、18 表/33 外键结构检查、40 条 OpenAPI 路径及真实 MySQL 版本 `1→2→3` 持久化验收通过
- 安全：所有 ProjectContext 和节点接口要求 JWT，Service 校验 Project 所有权；节点配置只能缩小字段白名单，外部 JSON 限制大小、深度并拒绝密码、Token、Secret、API Key 和原始模型输入键
- 已知限制：通用 `verify-backend.ps1` 固定调用系统 Python 的 `pytest`，与本仓库 `.venv + unittest` 约定不兼容；未新增 pytest、Ruff 或 Mypy 依赖，项目自身标准验证命令已通过

## 2026-09-02 13:07:47 +08:00

- 操作：完成 P11 统一 AI Provider、DeepSeek HTTP 适配、可靠性边界和受认证测试接口
- 目标：建立 `Router → AIService → AIClient → AIProvider → DeepSeek` 调用链，统一输入输出、错误分类、超时、取消、受限重试和脱敏日志
- 原因：为 P12 Agent 和 P13 Workflow Engine 提供不扩散供应商响应对象的模型调用边界，本阶段不实现 Agent、Workflow 执行或 AI 记录持久化
- 结果：完成；新增 `POST /api/v1/ai/test`，缺少密钥返回可操作的 503，真实 DeepSeek 接口和完整 API 路径均返回统一 JSON
- 恢复方式：回退本阶段提交并移除 `httpx` 直接依赖；本次未修改数据库结构、迁移、业务数据或前端代码
- 验证：Python 编译、102 项后端测试、`pip check`、41 条 OpenAPI 路径、Fake Provider、HTTP Mock 和真实 DeepSeek API 路径通过；真实接口返回 200、模型 `deepseek-v4-flash`、`finish_reason=stop`
- 安全：密钥只从已忽略的 `backend/.env` 读取，未输出或写入代码、日志、报告；日志不记录 Authorization、完整 Prompt、模型正文或个人数据
- 依赖确认：用户明确批准新增 `httpx>=0.28,<1.0` 和 DeepSeek 方案；实际安装 `httpx 0.28.1`，未安装 OpenAI、Anthropic 或其他供应商 SDK
- 已知限制：首次 8-token 真实请求因最终 `content` 为空被适配器正确拒绝，改为 64 tokens 后直连和 API 路径均通过；Ruff、Mypy、Pytest 未配置且未新增

## 2026-09-02 18:58:32 +08:00

- 操作：完成 P12 BaseAgent、ProjectAnalysisAgent、PromptAgent、ProjectReviewAgent、结构化结果 API 与 AIRequest/AIResult 持久化
- 目标：让核心 Agent 读取 P10 ProjectContext，经 P11 AIClient/AIProvider 单回合调用模型，并由 Service 保存和按当前用户查询结果
- 原因：为后续 P13 Workflow Engine 提供经过 Schema 校验、可审计且不直接操作数据库的 Agent 边界，本阶段不执行 Workflow 或模型生成命令
- 结果：完成；新增 3 个运行接口和 1 个结果查询接口，系统规则、Context、用户输入和模型输出分界，原始输入只保存 SHA-256 哈希和安全元数据
- 恢复方式：回退本阶段提交；本次未新增依赖、未修改 `schema.sql`、SQLAlchemy Models、18 张表或前端代码，MySQL 验收临时数据已自动清理
- 验证：18 项 P12 专项测试、121 项后端全量测试、Python 编译、`pip check`、45 条 OpenAPI 路径、真实 MySQL 持久化与跨用户隔离验收通过
- 真实 Provider：DeepSeek 原生 JSON 模式下，ProjectAnalysisAgent 和 PromptAgent 均返回 `finish_reason=stop` 并通过 Pydantic Schema；未记录 API Key、完整 Prompt 或模型正文
- 安全：Agent 单回合、总超时和 3000-token 默认上限明确；关闭 thinking；敏感输入和敏感模型输出均拒绝；不执行 shell、SQL、文件、工具或模型生成命令
- 范围：按优先级只实现 3 个可验证核心 Agent；未提前实现 LearningPlanAgent、LearningReportAgent、WorkflowAgent 或 P13 Workflow Engine

## 2026-09-02 19:42:06 +08:00

- 操作：完成 P13 Workflow 执行引擎、三节点 Agent 注册、运行状态持久化、Context 更新和 Run 结果查询
- 目标：串联 `WorkflowService → WorkflowEngine → Registry → Agent → AIClient → Provider → ContextManager → Repository → MySQL`，提供有界、可观测、可恢复的执行流程
- 原因：在 P09 编辑器、P10 Context、P11 Provider 和 P12 Agent 之上形成可运行的 AI Workflow 核心，不提前进入 P14 报告和统计
- 结果：完成；新增运行、运行列表和运行详情接口，支持需求分析、技术栈分析、架构设计的 DAG 顺序执行，以及技术栈变化后的下游 stale 和受影响节点重新生成
- 恢复方式：回退本阶段提交；本次未新增依赖、未修改 `schema.sql`、SQLAlchemy Models、18 张表或前端代码，MySQL 验收临时数据已自动清理
- 验证：12 项 P13 专项测试、133 项后端全量测试、Python 编译、`pip check`、48 条 OpenAPI 路径、MySQL 连接和 18 表/33 外键结构检查通过
- MySQL 验收：Fake Provider 完成 3 节点首次运行和 2 节点重新生成，保存 5 条结构化节点结果；活跃重复运行被拒绝，过期运行、请求和节点可恢复，临时用户残留为 0
- 可靠性：节点、回合、并发、总超时和 completion-token 预算均有上限；协程取消向上传播并持久化为 cancelled；只有 P11 AIClient 对明确短暂失败执行有界重试
- 安全：运行和结果查询按 Workflow 所属 Project 校验当前用户；模型结果经 Pydantic Schema 验证，日志只记录关联 ID、状态、耗时、Token 和失败类别，不记录密钥、完整 Prompt 或模型正文
- 已知限制：P13 固定顺序执行且不支持条件边或跨进程主动取消；跨进程中断通过下一次运行的超时恢复处理，真实 Provider 未在本阶段重复调用
