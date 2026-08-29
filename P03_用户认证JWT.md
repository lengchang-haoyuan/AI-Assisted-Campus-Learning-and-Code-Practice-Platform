# 用户注册登录JWT

## AI执行规则
- 先检查现有代码，再修改。
- 只完成本进度点，不跳到后续阶段。
- 不破坏已有功能。
- 每完成一个子任务立即验证。
- 不硬编码密钥、密码、Token。
- 最后汇报：修改文件、启动命令、测试结果、已知问题、Git提交建议。


---

## 本进度点目标
完成注册、登录、当前用户。API：POST /api/v1/auth/register；POST /api/v1/auth/login；GET /api/v1/users/me。密码 Hash，JWT Secret 来自环境变量；Axios 自动加 Authorization: Bearer；无效 Token 返回 401；区分 401/403；处理重复用户名、错误密码。验收：注册→登录→Token→/users/me 完整跑通。Git：feat: implement jwt authentication

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
