# P12 核心 AI Agent：可直接投喂给 AI 的提示词

在 P10/P11 的基础上，实现第一版核心 AI Agent。Agent 是学习与开发助手，不是自动代写代码的机器人；本阶段不实现完整 Workflow Engine。

## 本阶段目标

实现统一 `BaseAgent`，接口类似 `async run(context: ProjectContext, input_data: dict) -> AgentResult`，并优先完成：`ProjectAnalysisAgent`、`PromptAgent`、`ProjectReviewAgent`。条件具备时再补充 `LearningPlanAgent`、`LearningReportAgent` 和 `WorkflowAgent`，不得为了数量牺牲可验证性。

ProjectAnalysis 输出需求拆解、技术难点、开发步骤、知识点和技术栈建议。PromptAgent 生成可执行开发 Prompt，必须结合语言、框架、环境、目录、输入输出、编码规范、数据库、API 和前后端关系。Review 输出完成情况、问题和下一步。所有结果使用明确 schema 结构化；Agent 不直接操作数据库，由服务层保存 `AIRequest`/`AIResult`。

## 安全、可靠性与验收

系统规则、用户输入、Context 和模型输出必须分界；不把模型生成内容当作权限或命令；不执行任意 shell/SQL；限制输入大小、模型回合、超时和成本。测试 fake Provider 下的成功、schema 解析失败、Provider 失败、超时、敏感信息边界和提示注入。验收：分析 Agent 和 Prompt Agent 能读取 Context 并返回结构化结果，结果可查询；建议提交：`feat: implement core ai agents`。

