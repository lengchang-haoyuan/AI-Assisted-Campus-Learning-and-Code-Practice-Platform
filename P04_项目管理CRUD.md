# 项目管理 CRUD

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
完成 Project REST CRUD：GET/POST /api/v1/projects，GET/PUT/DELETE /api/v1/projects/{id}。Project 至少覆盖 name、description、difficulty、language、framework、frontend、backend、database、requirements、output_requirement、owner、status、timestamps。必须登录；用户权限正确；分页；Pydantic 校验；Service/Repository 分层；返回 Schema；处理 404/403/422。验收：Swagger 或前端完成完整 CRUD。Git：feat: implement project crud

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
