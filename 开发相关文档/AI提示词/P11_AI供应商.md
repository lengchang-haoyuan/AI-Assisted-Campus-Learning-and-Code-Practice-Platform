# P11 统一 AI Provider：可直接投喂给 AI 的提示词

在 P10 的上下文基础上，建立统一的 AI 调用抽象。本阶段实现 Provider 和 AI Client 的可靠边界，可以真正接通一个 Provider，但不实现完整 Agent 和 Workflow Engine。

## 本阶段目标

形成 `Agent → AIService/AIClient → AIProvider → 模型` 的调用链。定义统一 Provider 接口和返回结构，支持模型名、temperature 等参数；API Key 从环境变量读取；第一版选择一个 Provider 实现，OpenAI、DeepSeek 或 Claude 的具体选择要依据可用配置并说明，其他 Provider 保持可扩展。

统一处理连接超时、总超时、取消、网络错误、模型错误、限流和格式错误；只对明确可重试且幂等的短暂失败做有界重试。记录 provider、model、status、latency 和失败类别，但日志不得记录密钥、Authorization、完整敏感 Prompt 或个人数据。不要把第三方 SDK 响应对象扩散到业务层。

## 验收

提供 fake Provider 测试和一个真实 Provider 的最小测试接口，做到输入 → Provider → 统一 JSON；没有 API Key 时给出安全、可操作的配置错误，不能伪造成功。建议提交：`feat: implement ai provider abstraction`。

