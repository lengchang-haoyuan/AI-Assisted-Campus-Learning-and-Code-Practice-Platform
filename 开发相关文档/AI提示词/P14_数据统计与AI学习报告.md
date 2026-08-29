# P14 数据统计与 AI 学习报告：可直接投喂给 AI 的提示词

在已有学习、项目、社区、Workflow、AI 记录基础上，实现真实数据统计和 AI 学习报告。本阶段必须使用数据库聚合，不能为了页面效果写死数据。

## 本阶段目标

后端实现 Statistics API：今日访问人数、今日完成任务人数、项目数量、提交/发布项目数量、社区互动数量、7/30 日趋势、项目完成趋势、社区活跃趋势和技术栈统计。接口至少覆盖 `/api/v1/statistics/today`、`trend`、`projects`、`tech-stacks`，按当前权限和统计口径返回稳定 JSON。查询要有时间边界、时区约定、索引和有界范围。

前端使用 ECharts 展示统计结果，处理加载、空数据、错误、长时间范围和响应式布局。实现 `LearningReportAgent`：输入学习记录、任务、项目、Workflow/AI 使用情况，输出并校验 `summary`、`achievement`、`problems`、`suggestions`、`structured_data`，保存到 `learning_reports`。报告生成失败时不能伪造成功，必须能查询失败状态或给出可重试结果。

## 验收

准备可说明来源的测试数据，验证数据库聚合结果与图表一致；生成并保存一份学习报告，刷新后仍可读取。增加统计 Service/API 测试和报告 Agent fake Provider 测试。建议提交：`feat: implement statistics and ai learning reports`。

