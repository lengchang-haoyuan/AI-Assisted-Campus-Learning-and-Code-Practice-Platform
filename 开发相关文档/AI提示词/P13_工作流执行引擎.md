# P13 Workflow 执行引擎：可直接投喂给 AI 的提示词

在 P09 编辑器、P10 Context、P11 Provider 和 P12 Agent 之上，串起 Workflow 执行引擎。本阶段是 AI Workflow 的核心，只实现有界、可观测、可恢复的执行流程。

## 本阶段目标

实现调用链：`POST /api/v1/workflows/{id}/run → WorkflowService → WorkflowEngine → Registry → Agent → Context → Prompt → AIClient → Provider → LLM → AgentResult → ContextManager → Workflow State → MySQL`。

实现节点/Agent 注册、依赖分析、可执行节点查找、节点执行、结果保存、Context 更新、`WorkflowRun`、状态管理、失败/stale 处理、基础重试或明确失败策略和关联日志。演示三节点：需求分析 → 技术栈分析 → 架构设计。技术栈改变后，依赖它的下游节点必须 stale，并支持重新生成受影响节点。运行接口必须校验 Project/Workflow 所有权和节点合法性。

## 可靠性要求

限制最大节点数、最大回合数、并发、总超时和模型预算；重试只用于明确安全的短暂失败；支持取消或至少明确不能取消的边界；重复运行不能造成不可控重复数据。模型结果必须 schema 校验，失败状态可查询，日志包含 run/node 关联 ID、耗时、终止原因和失败类别，不记录敏感内容。

## 验收

三节点 Workflow 能完整运行，节点结果和 Context 更新可查询；改变技术栈后下游被标记 stale，重新运行后恢复；fake Provider 测试覆盖成功、失败、超时、预算耗尽、非法结果和重复运行。建议提交：`feat: implement workflow execution engine`。

