# ProjectContext 上下文系统

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
建立共享上下文：project_name、language、framework、frontend、backend、database、difficulty、requirements、output_requirement，并允许 architecture/features/constraints 等扩展。实现 context_schema.py、project_context.py、context_manager.py、ContextBuilder。Context 与 Project 关联；节点读写 Context；记录版本/更新时间；支持 stale。核心场景：Python 改 Java 后，下游 Prompt/项目结构标记 stale。验收：Context 创建、读取、修改、保存、节点读取、过期识别。Git：feat: implement project context

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
