---
tags: [ScholarHub/AI]
updated: '2026-09-07'
---
# Workflow 可视化编辑器

Vue Flow 承担节点画布；Workflow 归属于 Project，节点、边、位置与配置保存到 MySQL。编辑器不直接访问模型。

## 当前页面能做什么

在 `/workflows` 创建流程并关联自己的项目；打开 `/workflows/:id` 添加节点、拖拽位置、连线、修改配置、删除节点/边、整图保存和读取。配置应用后可保存并运行 AI，查看运行状态、结构化结果和历史记录，也可续跑失败节点或明确重跑全部节点。

验收动作：添加“需求分析”和“技术栈分析”，连接后保存，刷新确认位置、配置、边仍然存在。

## 组件分工

- `WorkflowCanvas.vue`：画布交互。
- `WorkflowToolbar.vue`、`WorkflowNodeLibrary.vue`：命令和节点入口。
- `WorkflowNodeConfigPanel.vue`：配置编辑。
- `WorkflowResultPanel.vue`：图合法性检查面板。
- `WorkflowExecutionPanel.vue`、`useWorkflowExecution.ts`：运行命令、轮询、历史和 AI 结果面板。
- `src/stores/workflows.ts`、`src/api/workflows.ts`：状态与持久化请求。

## 图约束

`GET/PUT /api/v1/workflows/{id}/graph` 支持整图读写；节点、边还有独立 CRUD。编辑上限是 100 个节点、300 条边；拒绝不存在的节点、重复边、自环和循环。

Workflow 状态含 `draft/ready/running/completed/failed/stale`。修改节点类型、配置、代码或依赖会让受影响旧结果进入待更新状态。

实际可运行的六类节点与更小运行上限见 [[15-Workflow执行引擎]]；教学节点支持解题提示、代码讲解和答案评审，但不执行学生代码。

源码：`backend/app/services/workflow.py`、`app/schemas/workflow.py`、`app/models/workflow.py`；`frontend/src/views/WorkflowEditorView.vue`、`src/domain/workflow.ts`。

关联：[[07-项目管理]]、[[12-ProjectContext上下文]]、[[03-前端架构与页面]]。
