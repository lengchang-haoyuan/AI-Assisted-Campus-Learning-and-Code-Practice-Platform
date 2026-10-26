---
version: 1
slug: "frontend-src-views-practiceworkbenchview-vue"
primary_target: "frontend/src/views/PracticeWorkbenchView.vue"
related_targets: ["frontend/src/views/ProjectAIWorkspaceView.vue","frontend/src/styles/practice-workbench.css","frontend/src/components/PracticeFeedbackPanel.vue","frontend/src/components/ProjectContextCandidates.vue","route:/projects/:id/practice","route:/projects/:id/ai"]
---

# 项目准备与步骤式实践工作台 · S09

## Scope and Mode

只记录 `/projects/:id/ai` 的项目准备和 `/projects/:id/practice` 的步骤式实践工作台。采用 Operate：让学生维护已保存资料、读当前任务、提交实现、按需请求帮助，再由本人审阅结束。延续既有 Campus Studio 的森林墨色、暖白纸面、薄荷画布与原有控件；共享视觉规则由 DESIGN.md 提供。

## Audience, Job and Content

学生围绕自己的项目连续完成准备与实践。准备页维护 Context、本人已定技术、交付要求、材料与版本；结构化 JSON、字段来源和高级节点影响可展开查看。固定 Python CSV 模板是已批准任务的预览，保存一致资料后即可进入实践。旧需求分析与开发 Prompt 工具保留在独立折叠区。

“项目目标”直接显示 `project.description`，提供“在项目详情维护目标”和“刷新目标与资料”。刷新通过 `getProject` 与 `findProjectContext` 同时载入项目和资料，保留本页 Context 草稿；版本冲突时先核对最新内容，再由本人合并保存。

工作台先说明当前目标、当前步骤与下一动作，提供会话选择、创建新实践、代码提交、版本复制、按需 AI、取消和恢复。任务及审阅材料绑定实际会话、模板版本和所选提交；旧资料快照与历史提交保留自己的版本。

## Direction and Memorable Moment

准备页将固定模板入口与“目标与准备材料”置于主要阅读路径，已定技术与待选 AI 候选分开。任务不依赖先生成草案或拖拽高级节点。

工作台桌面左侧为任务与提交物，右侧依次呈现下一动作、编辑与提交、历史代码及审阅材料、本人确认和按需帮助。1040px 以下按同一阅读顺序堆叠；390px 延续该顺序。长代码保留原换行，在可聚焦的 `pre` 内滚动。五类审阅来源分别成段，不以同一“通过”标签合并。

关键操作是学生选回当前提交，阅读各来源材料后，勾选本人审阅并明确结束本次实践。历史版本只读与复制；操作和 AI 帮助针对当前提交。

## Sources and Confirmation

- 自我声明保留本人原值；输出值核对只比较提交的声明值与公开样例，并直接标明平台未执行代码。
- AI 辅助建议展示确切提交与请求引用，保留引用片段、建议自测、可选下一步、未取得建议及错误状态。Fake 结果带工程演示来源。
- 本人确认记录对当前材料的审阅；教师确认独立呈现正式来源或“未提供正式教师确认”。`completed` 表示本次审阅流程结束，不承诺代码正确、教师通过或掌握程度。
- 创建、查询、刷新、取消、恢复和本人确认本身不调用模型。implement 提交后可不请求建议直接审阅结束；understand 仍遵守 S08 的 READY 状态机，由本人显式请求本步说明后再确认。AI 操作明确确认用量，失败或恢复不自动重发。

## Candidate and State Boundaries

候选从所选 workflow、run、node、request 的确切旧结果读取，展示当前已定与候选字段差异；先勾选字段，再确认来源与差异。应用复用既有节点 Context 端点、批准字段策略和当前版本条件。过期来源、节点状态不符、未保存草稿或正在保存时不能写回。旧 WorkflowRun 可能已在运行中合并 Context，导致所选结果过期，此时保留来源与差异供只读参考。实践建议不写入 Context；本 surface 不新增 B 组建议应用接口。

载入中、无会话、无候选、请求运行、失败、取消、恢复安全等待与结束各有对应文字和可执行动作。未提交草稿离开前明确确认；切换账号、项目、会话或提交时重置相应选择与审阅确认。Auth Store 与 generation/token/revision/attempt 绑定约束异步结果，迟到响应不能替换当前对象；恢复读取已保存状态与安全等待点。

## Evidence and Remaining Decisions

实现依据为本 brief 关联源码；工程验证分层记录在 `开发相关文档/阶段报告/AI大数据改造/V2/S09-完成报告.md`。既有 `.impeccable/review/s09/` 桌面和390px截图展示标明 Mock 的测试页面。UI Mock、真实 MySQL/Fake API 和新进程只读恢复各证明对应工程行为，不能据此评价真实建议质量；历史自动评分质量仍未通过。

本记录仅收口 S09 局部 surface。新的 B 组建议映射与任务应用留待 S10 按阶段处理。
