# L3 AI 学习报告事实数字：可直接投喂给 AI

现在执行 ScholarHub [闭环缺口清单](../开发规划/20260927-项目逻辑与代码闭环缺口清单.md)中的 **L3**，只修复报告结构化事实数字与聚合来源不一致的风险。不开展收费模型质量评测，也不实施完整 P22。

## 检查边界并复现

读取 [聚合源 Repository](../../backend/app/repositories/learning_report.py)、[报告 Service](../../backend/app/services/learning_report.py)、[报告 Agent](../../backend/app/agents/learning_report.py)、[Source/Result Schema](../../backend/app/agents/learning_report_schemas.py)、[报告测试](../../backend/tests/test_learning_reports.py)和 [页面显示](../../frontend/src/views/AnalyticsView.vue)。

构造 Fake Provider 样例：JSON、枚举和数值范围均有效，但 total_learning_minutes 或 task_completion_rate 与传入 Source 不同。先证明当前输出是否仍能成为 completed 报告；区分 Agent 校验与 Service 持久化路径。

## 推荐事实映射

以下事实来自“本次生成实际使用的 Source”，不能在模型返回后重新查询数据库替换，以免数据漂移：

| 结果字段 | 来源 |
| --- | --- |
| total_learning_minutes | source.learning.total_minutes |
| active_days | source.learning.active_days |
| task_completion_rate | source.tasks.completion_rate |
| project_average_progress | source.projects.average_progress |
| workflow_success_rate | source.workflows.success_rate |
| ai_request_count | source.ai_usage.request_count |

performance_level、focus_areas、recommended_weekly_minutes 与文字分析是模型判断或建议，不要伪装成数据库事实，也不要用事实映射覆盖它们。

## 最小设计与实施

推荐由服务端把上述事实数字填入最终结果，保留现有字段结构；另一方案是逐项核对模型值并将不一致结果持久化为明确失败。先说明两种方案在兼容性、失败率和用户体验上的取舍及推荐，按照已有授权和共同约束实施。

- 核对 AIResult、LearningReport 和 API 显示值如何保持一致，不能只改前端或只覆盖其中一份存储。
- 继续执行已有模型输出结构、敏感信息校验和安全错误映射。
- 不批量改写历史报告，不重写迁移；如旧报告存在影响，列出存量处理选项并单独确认。
- 文字摘要仍可能出现事实偏差；本步修复不能被表述为消除所有 AI 幻觉。

## 验收

- 结构有效但事实错误的输出，不再以错误数字展示为已核实的 completed 报告；按确认方案得到正确事实或明确失败。
- 正确输出、零数据、部分零值与率值边界均正确，取值来源是同次 Source。
- 生成、保存、列表、详情与页面刷新使用一致结果；所有权隔离保持有效。
- 模型失败、格式无效、取消与重试状态按既有路径保留。
- 优先运行 tests.test_learning_reports，涉及共同 Agent 逻辑时补相关 tests.test_agents。隔离 MySQL 验证与页面刷新留有证据；未完成部分交给 L4。
- 如修改前端，运行既有类型检查、构建和报告事实卡片人工验收。

交付复现样例、确认方案、最小差异、回归证据与报告。技术流程通过只证明工程可靠性，不写真实教学效果结论。

## 本步共同约束

- 先读取当前工作区 AGENTS.md（如存在）、$stop-that-shit、$frontend-backend-code-standards 和相关最新报告；以当前 Git 和源码为准。先检查已有未提交修改，保留无关工作。
- 先扫描、先做最小复现、先写设计，只执行本文件对应的缺口。已修复的问题核对必要证据后直接记录，不重复重构；无法读取仓库时先要求提供目标目录或相关文件。
- 沿用 Vue 3 / TypeScript / FastAPI / SQLAlchemy / MySQL 和现有分层、错误语义、测试方式。新增或升级依赖、公共 API/持久化语义/数据库/安全策略变更，依工作区规则先说明事实、影响、选项和推荐方案并取得确认；已有明确授权不重复询问。需要确认时，先完成可审查的复现与最小设计，再把待决策项交给用户。
- 用 Fake Provider 或现有依赖替换隔离模型边界。未经本轮费用和数据外发授权，不调用收费 Provider；不读取或输出密钥、密码、Token、私人业务正文。
- 真实 MySQL 写入验收只使用已确认的专用隔离环境，不在当前业务库运行试验数据或自动清理。测试失败保留证据，不删断言、不放宽权限换取通过。
- 先跑相关测试；前端改动执行现有类型检查和构建。格式/Lint/安全检查仅使用项目已有命令，缺少或未运行时如实说明，不为凑检查新增工具。不自动提交、推送、发布或开始下一步。
- 中文操作日志使用现有“开发相关文档/开发日志/开发操作日志.md”，单次报告使用“开发相关文档/阶段报告/”。汇报当前基线、实际修改、决策、验证命令与结果、未完成项和提交建议；历史的 98/203 项通过不能写成本步新结果。

