# 核心 AI Agent

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
第一版控制为 ProjectAnalysisAgent、LearningPlanAgent、PromptAgent、ProjectReviewAgent、LearningReportAgent、WorkflowAgent（条件具备再做）。BaseAgent：async run(context: ProjectContext, input_data: dict) -> AgentResult。ProjectAnalysis 输出需求拆解、难点、步骤、知识、技术栈；PromptAgent 生成包含语言、框架、环境、目录、输入输出、编码规范、数据库、API、前后端关系的 Prompt；Review 输出完成情况、问题、下一步。Agent 不直接操作数据库，结果结构化并保存 AIRequest/AIResult。验收：至少分析 Agent 和 Prompt Agent 真运行并读取 Context。Git：feat: implement core ai agents

## 执行要求
1. 先扫描当前仓库并报告已有结构。
2. 如果已有实现，优先兼容而不是重写。
3. 先设计再编码；重要结构变化先说明。
4. 每完成一组功能运行测试。
5. 最终输出：
   - 修改/新增文件清单
   - 关键调用链
   - 启动命令
   - 测试命令与结果
   - 手工验收步骤
   - 已知问题
   - 建议 Git commit
