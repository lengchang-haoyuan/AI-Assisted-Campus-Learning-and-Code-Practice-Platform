# Workflow 可视化编辑器

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
只做编辑器，不接 AI。使用 Vue Flow 或既定方案。对象：Workflow、WorkflowNode、WorkflowEdge。状态：draft/ready/running/completed/failed/stale。实现创建、拖拽、删除、配置、连边、删除边、整图保存/读取、基础合法性校验。API：workflow CRUD、nodes CRUD、edges CRUD、PUT /workflows/{id}/graph。验收：需求分析→技术栈两个节点可拖拽连接，保存刷新后恢复。Git：feat: implement workflow editor

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
