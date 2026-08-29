# P10 ProjectContext 上下文系统：可直接投喂给 AI 的提示词

为 P09 的 Workflow 和后续 Agent 建立共享的 `ProjectContext`。本阶段不接真实模型，不实现完整 Workflow 执行。

## 本阶段目标

定义并实现上下文模型，至少包含：`project_name`、`language`、`framework`、`frontend`、`backend`、`database`、`difficulty`、`requirements`、`output_requirement`，并允许 `architecture`、`features`、`constraints` 等扩展。实现 `context_schema.py`、`project_context.py`、`context_manager.py`、`ContextBuilder` 或与现有目录职责等价的模块。

Context 必须与 Project 关联；节点能够读取和写入 Context；更新时记录版本、更新时间和来源；支持 `stale` 过期识别。定义字段合并、冲突、空值、版本和下游失效规则。核心场景：把语言从 Python 改为 Java 后，依赖该信息的项目结构和 Prompt 节点被标记 stale。

## 约束与验收

模型输入、节点结果和外部 JSON 都是不可信输入，必须 schema 校验；不能让节点任意覆盖无关字段或越权读取别人的 ProjectContext。不要接 Provider、真实 AI 或无限循环。验收：Context 创建、读取、修改、保存、节点读取和过期识别均有测试；建议提交：`feat: implement project context`。

