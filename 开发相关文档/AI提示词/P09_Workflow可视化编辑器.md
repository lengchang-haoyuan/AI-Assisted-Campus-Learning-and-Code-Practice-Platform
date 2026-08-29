# P09 Workflow 可视化编辑器：可直接投喂给 AI 的提示词

在已有后端基础和前端 Vue 基础上，实现 Workflow 的持久化和可视化编辑器。本阶段只做编辑器，不接 AI、不执行 Agent。

## 本阶段目标

使用项目已选定的 Vue Flow 或既定流程图方案，围绕 `Workflow`、`WorkflowNode`、`WorkflowEdge` 实现：创建、读取、更新、删除 Workflow；节点拖拽、添加、删除、配置；边连接、删除；整图保存和读取；基础合法性校验。状态支持 `draft/ready/running/completed/failed/stale`，但本阶段不触发真实运行。

后端提供 Workflow CRUD、nodes CRUD、edges CRUD 和 `PUT /api/v1/workflows/{id}/graph` 等接口，路径与 Schema 保持一致。前端拆分画布、工具栏、节点库、节点配置面板、结果面板和 Store；画布组件不直接调用 AI API。服务端校验 Workflow 所属 Project 和当前用户权限，限制节点/边数量，拒绝不存在节点、重复边、非法自环或形成不允许的循环。

## 验收

创建一个 Workflow，放置“需求分析”和“技术栈分析”两个节点，拖拽并连接，保存后刷新页面，节点、位置、配置和边仍正确恢复。增加图保存和基础合法性测试。建议提交：`feat: implement workflow editor`。

