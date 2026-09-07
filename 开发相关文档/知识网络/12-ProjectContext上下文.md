---
tags: [ScholarHub/AI, ScholarHub/数据]
updated: '2026-09-04'
---
# ProjectContext 上下文

Context 为 [[14-核心Agent]] 和 [[15-Workflow执行引擎]] 提供共享项目事实，持久化在 `projects.context_data`，归属和权限来自 Project。

## 包含什么

名称、语言、框架、前端、后端、数据库、难度、需求与输出要求；扩展为 `architecture/features/constraints/extensions`。同时保存 Schema 版本、业务版本、UTC 更新时间、来源和逐字段元数据。

## 更新规则

- 请求提交 `expected_version`，版本落后返回 409；没有实际变化不递增版本。
- 普通字段整体替换；可空字段通过 `null` 清空。
- `architecture/extensions` 使用 JSON Merge Patch，嵌套 `null` 删除键。
- Project 核心字段与 Context 更新保持事务一致；经旧 Project 接口直接修改核心字段时，Context 可报告过期，需同步后继续。
- 节点读写受类型白名单限制，节点配置只能缩小权限，不能扩大权限。

## 为什么会 stale

把语言从 Python 改为 Java 后，依赖语言的结构/Prompt 等节点及 DAG 下游应标记 `stale`。这是“之前的结果依赖旧事实”，不是“模型一定运行失败”。重新生成与运行控制见 [[15-Workflow执行引擎]]。

## 边界与入口

`POST/GET/PUT /api/v1/projects/{id}/context`；节点还有 `/context/read` 与 `/context/write` 入口。限制 JSON 大小、深度和未知字段，拒绝常见敏感键；键名检查不能代替调用前的内容审查。

当前主要通过 API 操作，没有独立完整前端编辑面板。

源码：`backend/app/context/context_schema.py`、`project_context.py`、`context_manager.py`；`app/services/project_context.py`、`app/repositories/project_context.py`。

关联：[[05-数据库实体关系]]、[[06-账号认证与权限]]、[[11-Workflow可视化编辑器]]、[[18-测试证据与答辩]]。
