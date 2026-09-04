# Workflow 执行引擎

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
串起 Workflow、Context、Agent、Provider。调用链：POST /workflows/{id}/run→WorkflowService→WorkflowEngine→Registry→Agent→Context→Prompt→AIClient→Provider→LLM→AgentResult→ContextManager→Workflow State→MySQL。实现节点/Agent 注册、依赖分析、可执行节点、执行、结果保存、Context 更新、WorkflowRun、失败/stale、基础重试或失败策略、日志。演示三节点：需求分析→技术栈→架构。技术栈改变后下游 stale，重新生成受影响节点。验收：三节点完整运行且结果可查询。Git：feat: implement workflow execution engine

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
