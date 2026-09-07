---
tags: [ScholarHub/AI]
updated: '2026-09-07'
---
# 核心 Agent

Agent 读取经过校验的 [[12-ProjectContext上下文]] 和用户输入，通过 [[13-AIProvider]] 获得结果，再按业务 Schema 校验；不直接写数据库，也不执行系统命令。

## 当前实现

| Agent | 作用 | 接口 |
| --- | --- | --- |
| ProjectAnalysisAgent | 需求拆解、难点、开发步骤、知识点与技术栈建议 | `POST /api/v1/agents/project-analysis` |
| PromptAgent | 结合项目上下文生成可执行的开发提示 | `POST /api/v1/agents/prompt` |
| ProjectReviewAgent | 完成情况、问题和下一步 | `POST /api/v1/agents/project-review` |
| LearningReportAgent | 根据聚合学习数据生成结构化报告 | 由 [[16-统计与AI学习报告]] 的报告 Service 调用 |
| ExerciseHintAgent | 针对练习题生成分层提示，不直接给完整答案 | 由 Workflow 教学节点调用 |
| CodeExplanationAgent | 结合题意讲解学生提供的代码 | 由 Workflow 教学节点调用 |
| AnswerReviewAgent | 静态评审代码并给出结论与修改建议 | 由 Workflow 教学节点调用 |

前三类结果通过 `GET /api/v1/agents/results/{request_id}` 查询；按当前用户隔离。独立 Agent 页面尚未完整接入。

## 保存边界

Service/Repository 保存 `AIRequest` 与 `AIResult`。请求保存输入哈希、Context 版本、模型、状态、耗时和 Token 用量，不保存原始敏感输入；结果必须先通过 Schema。

系统规则、Context、用户输入分区组织；模型返回内容不能被当作权限、SQL、shell 或自动执行命令。单回合、输入上限、超时和输出预算共同限制调用范围。

## 与 Workflow 的关系

独立 ProjectAnalysisAgent 不等于图中所有节点的通用实现。[[15-Workflow执行引擎]] 通过 Registry 装配六类专用节点 Agent，按依赖顺序运行。

源码：`backend/app/agents/base.py`、`schemas.py`、`project_analysis.py`、`prompt_agent.py`、`project_review.py`；`app/services/agent.py`、`app/repositories/agent.py`。

验证定位：`backend/tests/test_agents.py`、`test_learning_reports.py` 和 `backend/scripts/verify_agents.py`。

关联：[[05-数据库实体关系]]、[[18-测试证据与答辩]]、[[20-项目内容补齐]]。
