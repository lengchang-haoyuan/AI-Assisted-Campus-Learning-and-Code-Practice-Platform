# 数据统计与 AI 学习报告

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
统计真实数据：今日访问、任务完成、项目、提交、社区互动、7/30日趋势、项目完成趋势、社区活跃趋势、技术栈统计。后端 Statistics API 从数据库聚合，不写死；前端 ECharts。LearningReportAgent 输入学习记录、任务、项目、Workflow/AI 使用情况，输出 summary、achievement、problems、suggestions、structured_data 并保存 learning_reports。验收：测试数据→图表正确→生成并保存报告。Git：feat: implement statistics and ai learning reports

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
