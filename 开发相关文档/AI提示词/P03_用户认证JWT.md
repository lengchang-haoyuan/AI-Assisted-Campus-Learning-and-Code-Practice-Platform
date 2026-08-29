# P03 用户注册登录 JWT：可直接投喂给 AI 的提示词

在 P00 到 P02 的基础上，实现 `ScholarHub` 的认证闭环。本阶段只实现用户认证和当前用户，不实现其他业务。

## 本阶段目标

实现：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`

注册时保存密码 hash，登录成功返回 JWT。JWT Secret、过期时间和算法配置来自环境变量。前端 Axios 负责自动注入 `Authorization: Bearer <token>`，收到无效 Token 时清理登录状态并处理 401。必须区分 401 未认证和 403 无权限，并处理重复用户名、重复邮箱、错误密码和无效请求。

## 安全要求

- 不存储和返回明文密码、Token Secret 或完整认证头。
- 使用成熟密码 hash 和 JWT 机制，不自制密码学。
- `/users/me` 必须由后端依赖完成身份验证。
- 认证错误提示不能泄露用户是否存在等不必要信息。
- 前端登录状态只改善体验，不能代替后端授权。

## 执行要求与验收

先检查现有 Model、Schema、配置、依赖和前端基础。按 Router → Service → Repository → Security 分层实现，并增加成功、重复注册、错误密码、无效 Token、缺少 Token 的测试。验收必须完成：注册 → 登录 → 获取 Token → 请求 `/users/me`；建议提交：`feat: implement jwt authentication`。

