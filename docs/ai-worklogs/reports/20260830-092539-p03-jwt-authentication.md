# 任务完成报告：P03 用户注册登录 JWT

- 完成时间：2026-08-30 09:25:39 +08:00
- 任务范围：全栈认证基础
- 项目根目录：`ScholarHub`

## 需求摘要

在 P00-P02 基础上实现注册、登录和当前用户认证闭环。密码只能保存哈希，登录签发环境变量配置的 JWT，`/users/me` 必须后端验签；前端 Axios 自动添加 Bearer Token，并在 401 时清理登录状态。本阶段不实现其他业务或认证页面。

## 修改内容

- 实现 `POST /api/v1/auth/register`、`POST /api/v1/auth/login` 和 `GET /api/v1/users/me`。
- 使用 Argon2id 哈希密码，使用 HS256 JWT，校验 `sub`、`iat`、`exp` 和过期时间。
- 注册处理重复用户名、重复邮箱和唯一约束并发冲突；登录对未知用户和错误密码返回相同错误。
- 缺少、无效或过期 Token 返回 401；已认证但账号不可用返回 403。
- 前端增加认证 API、用户类型、Pinia Auth Store、`sessionStorage` Token 和 Axios 401 拦截器。
- CORS 增加本阶段所需的 POST 和 Authorization 请求头。

## 文件与架构变化

- `backend/app/core/config.py`、`security.py`：JWT 配置、Argon2id 和 Token 签发/解码。
- `backend/app/repositories/user.py`：用户查询、创建和唯一约束冲突转换。
- `backend/app/services/auth.py`：注册、登录、当前用户和账号状态规则。
- `backend/app/schemas/auth.py`、`user.py`：认证请求与响应 DTO，不暴露 ORM。
- `backend/app/api/deps.py`：Bearer Token、SecurityService、AuthService 和当前用户依赖。
- `backend/app/api/v1/auth.py`、`users.py`：认证传输边界。
- `frontend/src/auth/session.ts`、`stores/auth.ts`：Token 与当前用户状态。
- `frontend/src/api/client.ts`、`api/auth.ts`、`api/users.ts`：认证请求和 Axios 拦截。
- `backend/tests/test_auth.py`：密码、JWT、注册、登录、401/403 和输入测试。
- 调用链：Router → AuthService → UserRepository → User Model → MySQL；密码/JWT 由 AuthService 调用 SecurityService，不在 Router 或 Repository 实现。

## 关键设计决定

- 决定：新增 `pwdlib[argon2]` 和 `PyJWT`。
- 原因：使用成熟实现提供 Argon2id 密码哈希和受控 JWT 编解码，不自制密码学。
- 用户确认：用户在 2026-08-30 明确批准，并要求在报告中记录。
- 实际版本：`pwdlib 0.3.1`、`argon2-cffi 25.1.0`、`PyJWT 2.13.0`；依赖范围分别固定为 `pwdlib[argon2]>=0.3,<1.0` 和 `PyJWT>=2.10,<3.0`。
- 决定：登录使用 JSON `identifier + password`，identifier 支持用户名或邮箱。
- 原因：不使用 OAuth2 表单，因此不需要新增 `python-multipart`。
- 用户确认：不需要；符合项目接口文档和最小依赖原则。
- 决定：前端 Token 使用 `sessionStorage`，不使用长期 `localStorage`。
- 原因：满足当前标签页刷新恢复和 Axios 注入，同时减少浏览器会话结束后的持久暴露。
- 用户确认：不需要；提示词没有要求跨浏览器会话保持登录。

## 兼容性与安全影响

- 公共 API：新增三个 P03 API；health 和既有错误结构保持兼容。
- 数据与迁移：复用 `users.password_hash` 和现有唯一约束，无表结构或迁移变化。
- 配置：新增必填 `JWT_SECRET`，最少 32 字符；新增 `JWT_ALGORITHM=HS256` 和 `JWT_EXPIRE_MINUTES`。
- 密码：数据库仅保存 Argon2id 哈希；API 响应不包含 `password_hash`。
- Token：仅允许配置的 HS256，要求必要声明；日志和响应不输出 Token、Secret 或认证头。
- 认证语义：错误用户名/邮箱和错误密码均返回相同 401，避免不必要的账号存在性泄露；禁用账号返回 403。

## 验证结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 后端测试 | `python -m unittest discover -s tests -v` | 通过 | 24 项，含 P03 安全、Service、API 与既有回归测试 |
| Python 编译 | `python -m compileall -q app scripts tests` | 通过 | 后端模块均可编译 |
| Python 依赖 | `python -m pip check` | 通过 | 新增依赖无冲突 |
| 前端类型检查 | `pnpm typecheck` | 通过 | Axios 拦截器、API 和 Auth Store 类型通过 |
| 前端构建 | `pnpm build` | 通过 | Vite 生产构建成功 |
| 注册闭环 | 真实 HTTP + MySQL | 通过 | 注册 201，数据库写入用户 |
| 重复注册 | 真实 HTTP + MySQL | 通过 | 返回 409 |
| 错误密码 | 真实 HTTP + MySQL | 通过 | 返回 401，与未知用户使用相同消息 |
| 登录与当前用户 | 真实 HTTP + MySQL | 通过 | 返回 bearer Token，`/users/me` 返回 200 |
| 无效 Token | 真实 HTTP | 通过 | `/users/me` 返回 401 |
| 密码存储 | 真实 MySQL 查询 | 通过 | 以 `$argon2id$` 开头且不等于测试明文 |
| 验收清理 | 真实 MySQL 删除 | 通过 | 删除 1 个验收用户，无测试数据残留 |

## 未执行或未通过的检查

- 未增加前端单元测试框架；项目当前没有前端测试配置，本阶段通过 TypeScript 检查、生产构建和真实后端闭环验证前后端契约。
- 未运行 Ruff、Mypy 或 Pyright，因为项目尚未配置这些工具，且本阶段没有批准新增相关依赖或检查策略。
- 未制作登录和注册页面；P03 明确要求认证闭环和 Axios 状态，正式页面属于后续前端节点。

## 剩余风险与后续建议

- 当前只有短期访问 Token，没有刷新 Token、服务端撤销列表或跨设备会话管理；这些不属于 P03，后续若需要应单独设计存储和失效语义。
- `sessionStorage` 中的 Bearer Token 仍依赖前端避免 XSS；后续页面不得使用不安全 HTML 或记录 Token。
- 正式运行前必须在本地 `.env` 或部署环境配置独立随机的 `JWT_SECRET`，不能使用示例值或提交到仓库。

## 建议 Git commit 信息

`feat: implement jwt authentication`
