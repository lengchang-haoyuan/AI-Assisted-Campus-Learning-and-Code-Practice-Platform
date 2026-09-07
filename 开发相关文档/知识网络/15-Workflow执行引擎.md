---
tags: [ScholarHub/AI]
updated: '2026-09-07'
---
# Workflow 执行引擎

引擎把 [[11-Workflow可视化编辑器]] 中的合法 DAG、[[12-ProjectContext上下文]]、[[14-核心Agent]] 和 [[13-AIProvider]] 连接起来。

`运行 API → WorkflowService → Engine → Registry → Agent → AIClient → Provider → 结果校验 → ContextManager → Repository → MySQL`

## 实际可运行的节点

项目分析链：`requirements_analysis → tech_stack_analysis → architecture_design`

教学节点：`exercise_hint`、`code_explanation`、`answer_review`。

共六类实际注册节点。未注册类型和条件边不能冒充已支持；教学评审只分析用户提供的代码，不执行代码。

## 运行与恢复

- `POST /api/v1/workflows/{id}/run` 提交 `expected_version`。
- `mode=incomplete` 执行未成功节点及其受影响下游；`mode=all` 明确重跑整图。
- `GET /workflows/{id}/runs` 和 `/runs/{run_id}` 查询记录。
- 结果校验后，将节点输出、AIResult 与 Context 原子保存；远程请求不占用数据库长事务。
- 技术栈修改使下游架构过期，重跑生成受影响结果。

WorkflowRun 有 `pending/running/completed/failed/cancelled`；节点有 `pending/running/success/failed/stale`，不要把两种状态机混用。

## 有界执行

默认最多 12 节点、12 回合、9000 completion tokens、90 秒、并发 1，具体取决于环境配置。编辑图的 100 节点上限不代表可以运行 100 节点。

当前为顺序执行。协程取消有记录；没有跨进程取消接口。超时遗留的 running 记录在下一次运行时进行恢复判定，不是后台持续任务队列；没有 Redis 或 Celery。

前端工作流编辑器已经接入运行、轮询、历史分页、结构化结果、失败续跑和全部重跑；独立 Agent 页面仍不等于 Workflow 运行页。

源码：`backend/app/workflow/engine.py`、`registry.py`、`agents.py`；`app/api/deps.py`、`app/repositories/workflow_execution.py`。

关联：[[05-数据库实体关系]]、[[17-启动配置与安全]]、[[18-测试证据与答辩]]、[[19-开发进度与后续路线]]。
