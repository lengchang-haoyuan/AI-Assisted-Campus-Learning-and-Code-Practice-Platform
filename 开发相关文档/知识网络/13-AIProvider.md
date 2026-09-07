---
tags: [ScholarHub/AI]
updated: '2026-09-04'
---
# AI Provider

Provider 隔离外部模型协议，AIClient 管统一结果、超时、取消与有限重试。当前实现是 DeepSeek HTTP 适配器，不是同时接通多个供应商。

`Agent / AIService → AIClient → AIProvider → 模型 → 统一结果`

## 已有能力

- 统一请求携带模型、消息、temperature 和输出 Token 上限。
- 区分配置、网络、连接/总超时、限流、模型与响应格式失败。
- 只有被明确标记可重试的短暂安全失败进入有界退避；不对任意失败无限重试。
- 日志只记录 Provider、模型、状态、耗时、尝试次数和失败类别，不记录密钥、认证头和完整敏感 Prompt。

## 如何确认是否可用

`POST /api/v1/ai/test` 是需登录的最小连通性接口。实际调用依赖本地环境变量；没有 Key 返回安全的 503 配置错误，不会伪造成功。具体模型名以本地配置为准，本网络不读取真实密钥。

Fake Provider 用于可重复测试，不代表在线模型已被调用。真实调用需要可用配置、网络及明确费用范围；本轮文档整理未调用模型。

## 与 Agent 的分工

Provider 只负责模型传输和统一返回；[[14-核心Agent]] 负责业务输入、提示边界和结构化输出校验。第三方原始响应对象不向业务各层扩散。

源码：`backend/app/ai/provider.py`、`client.py`、`deepseek.py`；`app/services/ai.py`、`app/core/config.py`。

关联：[[15-Workflow执行引擎]]、[[16-统计与AI学习报告]]、[[17-启动配置与安全]]、[[18-测试证据与答辩]]。
