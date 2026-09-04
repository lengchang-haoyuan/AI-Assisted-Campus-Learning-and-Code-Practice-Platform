# 统一 AI Provider

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
建立 Agent→AIService/AIClient→AIProvider→模型的抽象。Provider 接口统一；API Key 从环境变量；支持 model/temperature；统一返回结构；捕获超时/网络/模型错误；记录 provider/model/status/latency；不要把 SDK 调用散落业务 Service。第一版真正接通一个 Provider，其余可扩展。验收：测试接口输入→模型→统一 JSON。Git：feat: implement ai provider abstraction

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
