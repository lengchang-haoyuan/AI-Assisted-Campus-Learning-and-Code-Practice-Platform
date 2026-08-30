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
