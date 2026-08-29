# P04 项目管理 CRUD：可直接投喂给 AI 的提示词

基于前四个阶段，实现 `Project` 的 REST CRUD。本阶段只完成项目管理，不实现社区互动、Workflow 执行和 AI 功能。

## 本阶段目标

实现：`GET/POST /api/v1/projects`、`GET/PUT/DELETE /api/v1/projects/{id}`。Project 至少包含 `name`、`description`、`difficulty`、`language`、`framework`、`frontend`、`backend`、`database`、`requirements`、`output_requirement`、`owner`、`status` 和时间字段。

所有接口必须登录；创建项目的 owner 来自当前用户，不能由客户端伪造。更新和删除必须在服务端校验资源所有权。列表支持有界分页、稳定排序和明确的空数据语义。Pydantic 校验名称、长度、状态、难度、分页边界和可选字段，返回独立 Response Schema。

## 错误与验证

明确处理 401、403、404、409、422 和内部错误；不能“先查资源再忘记校验 owner”。Repository 负责查询，Service 负责业务规则，Router 只做输入、认证、调用和响应映射。增加 API 和 Service 测试，覆盖创建、列表、详情、更新、删除、分页、越权和不存在资源。

先扫描前后端现状并保持兼容。验收可通过 Swagger 或前端完成完整 CRUD，数据刷新后仍来自数据库。建议提交：`feat: implement project crud`。

