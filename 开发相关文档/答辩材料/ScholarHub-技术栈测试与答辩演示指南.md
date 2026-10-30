# ScholarHub 技术栈、系统防御性测试与答辩演示指南

> 文档日期：2026-10-29
>
> 适用项目：ScholarHub 当前工作区
>
> 建议毕设题目：基于 Spark 的校园代码学习行为分析与可视化系统的设计与实现

## 1. 先给结论

ScholarHub 不是只有一个前后端 CRUD，而是一个“校园代码学习业务平台 + AI 辅助实践 + Spark 离线学习行为分析”的交叉项目。

答辩时建议使用下面这组统一口径：

- 项目可以分成 6 大技术域。
- 核心运行与架构口径共 31 项技术或关键组件。
- 如果把测试、构建和验证工具也计算在内，共 36 项工程要素。
- 当前后端有 38 个测试文件、433 个具名测试方法。
- 2026-10-29 在项目自带 Python 3.12 虚拟环境中复跑：433 项全部通过，耗时约 14.6 秒。
- 按测试名称中明确出现的拒绝、权限、越权、并发、幂等、回放、超时、回滚、敏感信息、输入边界等词进行保守静态统计，至少 319 项属于防御、异常或边界测试，占 73.7%。这是可复核的下限，不是代码覆盖率。
- 当前前端 typecheck 与 production build 均通过；构建存在一个 ECharts 分包大于 500 kB 的警告，不是构建失败。
- Spark 的核心职责是把固定 ODS 快照转换成可核验的 DWD 事实层和 ADS 指标层，再发布给只读 API 和 ECharts 页面；普通页面刷新不会启动 Spark。
- 当前 Spark 是 WSL2 中的 PySpark 4.2.0、Java 17、local[2] 单机离线批处理，不是实时计算，也不是多机集群。

## 2. 项目技术定位

### 2.1 一句话定位

ScholarHub 是面向校园代码学习场景的全栈平台：学生可以管理项目、计划和任务，参加教学班、提交成果并接收教师反馈；系统还提供 AI 辅助工作流与代码实践，并通过 Spark 对固定时间窗口内的学习记录、任务进度、提交修订和实践过程进行离线分析与可视化。

### 2.2 为什么是交叉型项目

| 方向 | 项目中的落点 |
| --- | --- |
| 前端 | 学习工作台、教学班、社区、工作流画布、实践工作台、分析图表 |
| 后端 | FastAPI 接口、业务服务、仓储、鉴权、事务与错误契约 |
| 数据库 | MySQL 业务数据、约束、外键、事务、批次发布 |
| AI / Agent | Provider 抽象、结构化输出、Agent、DAG Workflow、PracticeSession |
| 大数据 | 固定快照、ODS、PySpark DWD、Spark SQL ADS、Parquet、规模实验 |
| 测试与防御 | 权限、并发、幂等、失败恢复、模型边界、数据质量、浏览器验收 |

## 3. 技术栈到底有多少个

“技术栈有多少个”没有唯一标准：Vue Router 可以算 Vue 生态的一部分，也可以单独算一项。为了答辩时前后一致，本文采用“可以独立说明职责的技术或关键组件”口径。

### 3.1 核心技术与组件：31 项

| 技术域 | 数量 | 技术或组件 | 在项目中的作用 |
| --- | ---: | --- | --- |
| 前端 | 9 | Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、Vue Flow、ECharts | 页面与组件、类型、构建、路由、状态、HTTP、UI、工作流画布、图表 |
| 后端与 API | 8 | Python、FastAPI、Pydantic、pydantic-settings、SQLAlchemy、PyMySQL、Uvicorn、HTTPX | API、校验、配置、ORM、MySQL 驱动、服务运行、外部 HTTP |
| 数据与安全 | 3 | MySQL 8、JWT / PyJWT、pwdlib + Argon2 | 持久化、会话鉴权、密码哈希 |
| AI 与流程 | 4 | DeepSeek、AIProvider、AIClient、Agent + DAG Workflow | 模型适配、超时重试、结构化结果、有限状态流程 |
| 大数据与离线分析 | 7 | WSL2、Ubuntu 24.04、PySpark 4.2.0、Spark SQL、Java 17、JSONL、Parquet | Linux 运行环境、分布式计算接口、SQL 聚合、输入快照和列式产物 |
| 合计 | 31 | — | 答辩建议使用的核心口径 |

当前依赖证据：

- [前端 package.json](../../frontend/package.json)
- [后端 requirements.txt](../../backend/requirements.txt)
- [Spark 主入口](../../analytics/spark_job.py)
- [FastAPI 应用入口](../../backend/app/main.py)

### 3.2 再加 5 项测试与工程工具：共 36 项

| 工具或方法 | 作用 |
| --- | --- |
| unittest | 后端单元、服务、API 和回归测试 |
| Fake / Stub Provider | 不调用真实模型时验证 AI 编排、状态和结构化输出 |
| Playwright / Edge 验证脚本 | 浏览器真实交互、响应式和失败状态验收 |
| vue-tsc | Vue + TypeScript 类型检查 |
| pnpm | 前端依赖和脚本管理 |

这 5 项是工程保障，不建议与 31 项核心运行技术混在一句话里。最稳妥的回答是：“项目有 6 大技术域，31 项核心技术或组件；把测试构建工具算上是 36 项工程要素。”

## 4. 系统架构与真实调用路线

### 4.1 在线业务主链

浏览器页面 → Vue Router → Pinia / 组合式状态 → Axios → FastAPI Router → Service → Repository → SQLAlchemy → MySQL

关键入口：

- [前端入口](../../frontend/src/main.ts)
- [前端路由](../../frontend/src/router/index.ts)
- [HTTP 客户端](../../frontend/src/api/client.ts)
- [后端 API 总路由](../../backend/app/api/v1/router.py)
- [后端服务层](../../backend/app/services)
- [后端仓储层](../../backend/app/repositories)
- [数据库模型](../../backend/app/models)

### 4.2 AI 辅助主链

页面发起请求 → FastAPI → 业务 Service → Agent / Practice / Workflow → AIClient → AIProvider → DeepSeek → Pydantic 结构校验 → 保存结果或明确失败

关键入口：

- [Provider 接口](../../backend/app/ai/provider.py)
- [AIClient](../../backend/app/ai/client.py)
- [DeepSeek 适配器](../../backend/app/ai/deepseek.py)
- [Workflow Engine](../../backend/app/workflow/engine.py)
- [Practice 服务](../../backend/app/services/practice.py)

边界必须讲清：

- AI 输出是不可信输入，必须经过结构化校验。
- Fake Provider 证明工程流程、状态和错误处理，不证明真实模型质量。
- 系统当前不执行学生提交的任意代码；代码建议或评审属于静态辅助。
- AI 建议、学生确认和教师评价不是同一件事，不能把“本人确认”说成“教师通过”。

### 4.3 Spark 离线主链

MySQL 业务数据 → 只读一致性快照 → ODS JSONL → PySpark 清洗和关联 → DWD Parquet → Spark SQL 聚合 → ADS Parquet / JSON → 质量校验和独立答案对照 → 分析批次发布 → FastAPI 只读查询 → ECharts 展示

关键入口按顺序阅读：

1. [ODS 快照导出](../../backend/scripts/export_ods_snapshot.py)
2. [快照文件生命周期](../../analytics/snapshot_files.py)
3. [Spark 主任务](../../analytics/spark_job.py)
4. [学习过程 SQL](../../analytics/learning_process.sql)
5. [Spark 数据质量](../../analytics/spark_quality.py)
6. [独立标准答案](../../analytics/fixture_answers.py)
7. [发布输入准备](../../analytics/prepare_publication.py)
8. [后端批次服务](../../backend/app/services/analytics.py)
9. [后端分析 API](../../backend/app/api/v1/analytics.py)
10. [前端分析页面](../../frontend/src/views/OfflineAnalyticsView.vue)

## 5. Spark 在这个项目中到底起什么作用

### 5.1 Spark 解决的不是“网页展示”，而是离线指标加工

Spark 不负责登录、项目 CRUD、教学班、AI 对话或页面渲染。它负责把多个业务表在固定观察窗口内转换成统一、可追溯的学习过程事实与指标。

主要分析维度：

| 分析对象 | 指标示例 | 不能过度解释成什么 |
| --- | --- | --- |
| 学习记录 | 有效记录数、已知分钟、缺失时长、活跃天数、来源类型 | 不能直接等同于掌握程度 |
| 学习任务 | 总数、完成、取消、逾期未完成、完成率 | 完成率不是学习质量 |
| 教学提交 | 修订次数、教师确认、待评、首次反馈等待分布 | 修订后确认不能直接证明能力提升 |
| AI 实践过程 | 会话、尝试、提交、建议、确认等事件汇总 | AI 建议不等于代码正确或教师认可 |
| 时间 | 按 Asia/Shanghai 业务日期形成日趋势 | 页面展示时间不能反推原始事件顺序 |

### 5.2 为什么先做 ODS 快照

如果 Spark 直接连接不断变化的业务库，同一次分析可能前后读到不同数据，结果难以复现。项目先在 MySQL 的只读一致性事务中冻结窗口、用户、截止时间和源表行，再发布完整快照。Spark 只消费固定 ODS，不连接业务数据库。

这样做的价值：

- 可复现：同一 snapshot_id 可以重复计算和对照。
- 可追溯：输出保留 snapshot_id、job_id、规则版本和时间窗口。
- 可隔离：分析失败不会阻塞在线业务。
- 可审计：可以比较源表计数、DWD 计数、ADS 指标和独立答案。

### 5.3 DWD 和 ADS 的区别

- DWD 是清洗、去重、关联后的事实层，例如 record_facts、task_facts、cohort_facts。
- ADS 是面向页面和答辩问题的聚合层，例如学习记录汇总、任务完成率、修订与确认比例、每日趋势。
- 页面只读取已经发布的 ADS 批次，不负责临时重算指标。

### 5.4 为什么页面刷新不启动 Spark

分析 API 的 GET 请求读取 immutable completed batch。这样可以避免用户每次刷新页面都占用 Spark、等待几十秒或得到不一致结果，也避免在 Web 请求中执行大计算。

答辩时可以直接说：

> 我把在线业务和离线计算解耦了。Spark 先在后台消费固定快照，产生带版本和血缘的 DWD、ADS 产物，校验通过后再发布。前端只读已完成批次，所以页面刷新不会重跑 Spark，也不会触发模型或写数据库。

### 5.5 规模实验说明了什么

历史 S06 离线实验使用同一台机器、local[2]、driver 2 GiB、shuffle 8，比较 Python 标准库参考实现与 PySpark：

| 规模 | Python hot 中位数 | Spark hot 中位数 | 可以得到的结论 |
| ---: | ---: | ---: | --- |
| 1 万条 | 约 0.78 秒 | 约 16.39 秒 | 小数据下 Spark 启动和调度成本明显，Python 更快 |
| 10 万条 | 约 98.69 秒 | 约 23.18 秒 | 在该固定样本和本机条件下，Spark hot 约为 Python 的 4.26 倍速度 |

冷进程外部耗时在 10 万条时约为 Python 92.48 秒、Spark 39.46 秒，Spark 约为 2.34 倍速度。这个实验只能说明本机固定样本下的趋势，不能声称已经证明百万级、多机集群或生产吞吐。

证据：

- [S06 实验 QA](../阶段报告/AI大数据改造/V2/S06-实验/qa.json)
- [1 万条摘要](../阶段报告/AI大数据改造/V2/S06-实验/n10000-summary.json)
- [10 万条摘要](../阶段报告/AI大数据改造/V2/S06-实验/n100000-summary.json)

## 6. 做了多少系统防御性测试

### 6.1 当前可复核数字

| 项目 | 当前数字 | 说明 |
| --- | ---: | --- |
| 后端测试文件 | 38 | backend/tests/test_*.py |
| 具名测试方法 | 433 | 静态扫描 def test_* 与 async def test_* |
| 本轮实际通过 | 433 / 433 | 2026-10-29，项目 backend/.venv，约 14.6 秒 |
| 防御 / 异常 / 边界测试下限 | 319 | 按测试名保守关键词去重统计，占 73.7% |
| 前端类型检查 | 通过 | pnpm typecheck |
| 前端生产构建 | 通过 | pnpm build；存在 ECharts 大分包警告 |

这里的 319 不是随意估计：只统计名称中直接表现防御语义的测试，例如 reject、invalid、missing、conflict、replay、stale、timeout、rollback、authentication、ownership、sensitive、boundary、concurrent、idempotent 等。没有这些词但实际也在保护不变量的测试没有强行计入，因此它是下限。

### 6.2 防御性测试覆盖的十类问题

| 类别 | 代表场景 | 代表测试文件 |
| --- | --- | --- |
| 认证与会话 | 缺失 / 伪造 Token、短 JWT Secret、滑块一次性 Token、过期与重放 | [test_auth.py](../../backend/tests/test_auth.py)、[test_slider_captcha.py](../../backend/tests/test_slider_captcha.py) |
| 资源授权与隔离 | 项目所有权、跨班级访问、不同教师 / 学生隔离、他人会话不可读写 | [test_teaching.py](../../backend/tests/test_teaching.py)、[test_campus_identity.py](../../backend/tests/test_campus_identity.py) |
| 输入与 API 边界 | 空值、额外字段、非法 ID、日期、时区、URL、分页、稳定错误结构 | [test_api_foundation.py](../../backend/tests/test_api_foundation.py)、[test_workspace.py](../../backend/tests/test_workspace.py) |
| 业务状态机 | 已取消任务不能完成、终态计划不能被破坏、归档状态拒绝写入 | [test_learning.py](../../backend/tests/test_learning.py)、[test_audit_regressions.py](../../backend/tests/test_audit_regressions.py) |
| 并发与事务 | 锁释放、异常回滚、双连接并发、同一批次只创建一次、无部分保存 | [test_workflow_run_edit_guard.py](../../backend/tests/test_workflow_run_edit_guard.py)、[test_audit_regressions.py](../../backend/tests/test_audit_regressions.py) |
| 幂等与重放 | 重复完成、重复发布、重复反馈、相同 operation 重放不重复调用模型 | [test_practice_service.py](../../backend/tests/test_practice_service.py)、[test_submissions.py](../../backend/tests/test_submissions.py) |
| AI 安全与可靠性 | 提示注入边界、敏感输入 / 输出、结构解析失败、只重试可重试错误、总超时 | [test_ai_provider.py](../../backend/tests/test_ai_provider.py)、[test_agents.py](../../backend/tests/test_agents.py) |
| Workflow 版本防护 | 运行中禁止改图、旧版本结果不能覆盖新版本、失败后释放编辑保护 | [test_workflow_run_edit_guard.py](../../backend/tests/test_workflow_run_edit_guard.py)、[test_workflow_invalidation.py](../../backend/tests/test_workflow_invalidation.py) |
| Spark 数据质量 | 重复、缺失、跨主体关联、时间窗口、版本、质量失败不发布、层间计数对账 | [test_analytics.py](../../backend/tests/test_analytics.py)、[test_ods_snapshot.py](../../backend/tests/test_ods_snapshot.py)、[test_s10_pipeline.py](../../backend/tests/test_s10_pipeline.py) |
| 编码与运行环境 | UTF-8 中文 / Emoji、子进程继承、时区转换和 naive datetime 拒绝 | [test_utf8_output.py](../../backend/tests/test_utf8_output.py)、[test_database_schema.py](../../backend/tests/test_database_schema.py) |

### 6.3 测试证据必须分层

不要把所有“通过”混成一句话。答辩时按下面四层讲：

1. 单元、Fake 和 API 契约层：本轮 433 项全部通过，主要证明业务规则、接口语义、异常与编排。
2. 真实 MySQL 层：历史隔离库验证过双连接并发、事务回滚、发布幂等、跨用户隔离和无部分写入；它不是本轮重新执行。
3. 浏览器层：历史 S06 使用真实 TCP API 和认证 MySQL 验证过桌面 / 移动端、空批次、199/200 边界、网络失败保留旧数据等；它不是本轮重新执行。
4. Spark 层：历史离线实验完成 28 轮，其中 24 轮计量、14 个 Spark 作业和独立答案对照；不包含真实模型调用、业务库连接、百万档或集群。

当前 ORM 元数据静态加载得到 40 张表、106 个外键。历史 S05 验证当时是 36 张表，不能把旧数字说成当前数据库实跑结果。

历史浏览器证据：[S06 浏览器验收](../阶段报告/AI大数据改造/V2/S06-验证证据/browser/final/verification.json)

## 7. 答辩演示主路线：12 分钟

### 7.1 演示前准备

- 提前启动 MySQL、后端和前端，确认 3306、8000、5173 端口可用。
- 后端健康检查应返回 200：/api/v1/health。
- 准备固定学生账号、教师账号、教学班、任务、提交和已发布分析批次。
- 预先打开登录页、实践工作台、我的学习洞察三个标签页。
- Spark 产物提前计算并发布，不建议答辩现场等待 Spark 冷启动。
- 把批次 b96ea63e-419e-4293-b724-d1ce59bd85ba 作为历史固定演示批次；演示前再次确认当前数据库仍保留该批次。
- 准备浏览器验收截图和 1 万 / 10 万实验图作为断网或服务失败备用材料。

### 7.2 0:00—1:00：项目定位

口播：

> 我的项目面向校园代码学习场景，在线部分用 Vue 3、FastAPI 和 MySQL 支撑项目、计划、教学班、提交反馈、社区和 AI 辅助实践；离线部分使用 PySpark 对固定快照进行清洗、关联和聚合，形成可追溯的学习行为指标，再通过只读 API 和 ECharts 展示。项目重点不是堆功能，而是把业务闭环、AI 边界、数据一致性和离线分析串成一条可验证链路。

操作：登录学生账号，快速展示导航和工作台，不在首页停留太久。

### 7.3 1:00—3:30：校园学习业务闭环

操作顺序：

1. 打开教学班或任务。
2. 展示学生提交成果。
3. 展示教师退回、学生修订、教师确认的历史链。
4. 指出每次提交和反馈都保留版本，不覆盖旧记录。

老师应看到的价值：分析指标不是凭空生成，而是来自真实业务过程事件。

### 7.4 3:30—6:00：AI 辅助实践

操作顺序：

1. 打开 Practice 工作台或已保存会话。
2. 展示提示、解释或评审建议。
3. 展示学生提交、修订和确认状态。
4. 指出系统保存 operation、revision、attempt 和事件历史，重复请求不会重复调用模型。

必须主动说明：

> AI 在这里提供辅助建议，不直接执行学生代码，也不自动代表教师判定。模型结果要经过结构化校验，失败、超时、取消和迟到响应都有明确状态。

### 7.5 6:00—9:30：Spark 学习行为分析

操作顺序：

1. 打开“我的学习洞察”。
2. 选择已发布批次，展示时间窗口和批次来源。
3. 展示 90 分钟、5 条有效记录、2 个活跃日、2/4 任务完成、1 个逾期未完成等固定批次数据。
4. 展示按日趋势、任务、提交修订和教师反馈图表。
5. 切换 199/200 边界批次，说明完成率是 99.5%，不是被四舍五入成 100%。
6. 刷新页面，说明这里只读取已发布批次，不会重跑 Spark、调用模型或写数据库。

Spark 口播：

> 业务库先通过只读一致性事务冻结 ODS 快照，Spark 再做去重、关系校验和 DWD 事实建模，随后用 Spark SQL 生成 ADS 指标。产物只有在 fatal_errors 为 0、层间计数对账成功并与独立标准答案一致后才能发布。这样页面看到的不只是图，而是有快照、规则版本、作业 ID 和质量门槛的结果。

### 7.6 9:30—11:00：规模实验与技术取舍

展示 1 万和 10 万实验图：

- 1 万条时 Python 更快，说明 Spark 有启动和调度成本。
- 10 万条时 Spark hot 约 23.18 秒，Python hot 约 98.69 秒，说明数据规模上升后并行计算开始体现优势。
- 主动说明 local[2] 是单机并行，不是集群；百万档和集群仍待验证。

这段比单纯说“Spark 很快”更可信。

### 7.7 11:00—12:00：系统防御与收尾

口播：

> 当前后端有 433 个自动化测试，本轮全部通过。其中至少 319 个测试名直接体现权限、边界、并发、幂等、回放、超时、回滚或敏感数据等防御语义。除此之外还有历史真实 MySQL、浏览器和 Spark 分层证据。我不会把 Fake Provider 通过说成真实模型质量，也不会把 local[2] 说成多机集群。

最后回到项目题目：校园代码学习业务产生数据，Spark 对学习过程进行离线分析，前端完成可视化和答辩展示。

## 8. 演示故障时怎么兜底

| 故障 | 现场处理 | 不要做什么 |
| --- | --- | --- |
| DeepSeek 超时或断网 | 展示已保存会话和 Fake 编排测试证据，说明真实模型质量另验 | 不要连续重试或声称 Fake 等于真实模型 |
| Spark 冷启动慢 | 直接展示已发布批次、manifest、DWD / ADS 产物和实验图 | 不要临场重新导出业务库和跑全量实验 |
| MySQL 服务异常 | 用固定浏览器截图、发布结果 JSON 和 API 验收证据继续讲链路 | 不要切换到未知数据库或清空业务库 |
| 浏览器页面异常 | 打开 Swagger /docs 展示只读分析 API，再展示历史截图 | 不要现场改代码 |
| 老师追问是否集群 | 明确回答 local[2] 单机双线程，架构可迁移但未验证集群 | 不要把 WSL2 包装成集群 |
| 老师追问学习效果 | 回答当前指标描述学习过程，不证明知识掌握或因果提升 | 不要把修订率、完成率当学习效果 |

## 9. 想完全吃透项目，还需要做什么

建议按 7 个阶段学习，共约 40—60 小时。每次只学一个阶段，达到验收条件再进入下一阶段。

### 阶段 1：讲清业务与角色，4—6 小时

要学：学生、教师、校园管理员、项目、计划、任务、教学班、作业、提交、反馈、社区、AI 会话、分析批次之间的关系。

阅读：

- [API 总路由](../../backend/app/api/v1/router.py)
- [数据库模型目录](../../backend/app/models)
- [前端路由](../../frontend/src/router/index.ts)

验收：不看文档，能在 3 分钟内画出“学生提交 → 教师反馈 → 学生修订 → 分析指标”的业务链。

### 阶段 2：吃透一条前后端垂直链，6—8 小时

建议选“学习任务”或“离线分析批次”，从页面按钮一直追到数据库查询。

阅读顺序：View → composable / store → api → FastAPI router → schema → service → repository → model。

验收：能解释一次请求的输入校验、鉴权、业务规则、事务、错误状态码和前端错误展示。

### 阶段 3：吃透数据库与事务，6—8 小时

要学：40 张表的领域分组，不必死背全部字段；重点理解主外键、唯一约束、状态字段、版本字段、批次身份和删除语义。

重点：

- 为什么权限过滤应进入查询条件。
- 为什么模型等待不能占着数据库锁。
- 为什么幂等发布需要唯一身份与重放语义。
- 为什么失败不能留下部分日汇总。

验收：能解释两个并发请求为什么不会生成两个相同批次，也能解释异常时如何回滚。

### 阶段 4：吃透 AI / Workflow / Practice，8—10 小时

阅读：

- [AIProvider](../../backend/app/ai/provider.py)
- [AIClient](../../backend/app/ai/client.py)
- [Workflow Engine](../../backend/app/workflow/engine.py)
- [Practice Service](../../backend/app/services/practice.py)

必须掌握：结构化输出、提示注入边界、敏感信息拒绝、超时、有限重试、取消、预算、版本冲突、迟到响应隔离、operation replay。

验收：能回答“为什么不直接在 Controller 里调用 DeepSeek”和“模型返回 JSON 为什么仍不能直接信任”。

### 阶段 5：完整手推 Spark 数据链，10—12 小时

做法：选固定 S06 主批次，手工追一条 learning_record、一个 task 和一次 submission / feedback，依次找到 ODS 行、DWD 事实、ADS 指标、发布 payload 和页面展示。

必须掌握：

- 一致性快照和 source_cutoff。
- ODS、DWD、ADS 的职责。
- 去重、NULL 时长、0 时长、取消任务分母、199/200 精度。
- layer reconciliation 与 independent answer 的区别。
- local[2]、shuffle partitions、Parquet 和 Spark SQL。

验收：给你一个错误指标时，你能判断应该查 ODS、DWD、ADS、发布还是前端格式化。

### 阶段 6：理解防御性测试，4—6 小时

从 319 个防御性场景中每类挑 2 个，不是背测试名，而是说清“攻击或错误输入 → 系统保护 → 预期状态和数据”。

重点练习：

- 越权读写。
- 重放与幂等。
- 并发更新和旧结果覆盖。
- AI 超时、无效结构和提示注入。
- Spark 数据质量失败不发布。

验收：老师随机问一个异常，你能指出保护发生在前端、API、Service、Repository、数据库约束还是离线质量门。

### 阶段 7：脱稿答辩与故障演练，4—8 小时

至少完成三轮：

1. 12 分钟正常演示。
2. 断网、不调用模型的备用演示。
3. MySQL 或前端不可用，只靠 API、JSON、截图和源码的证据演示。

验收：每轮不超过规定时间；不说“实时 Spark”“多机集群”“AI 自动判对”“完成率证明学习效果”等越界表述。

## 10. 老师高频追问与答题要点

### 10.1 为什么用 Spark，MySQL GROUP BY 不行吗

回答要点：小数据当然可以用 MySQL 或 Python，所以项目没有声称 Spark 在所有规模都更快。选择 Spark 是为了建立可扩展的离线分层计算链、固定快照复现、跨表清洗关联、Parquet 产物和规模实验。1 万条时 Spark 反而慢，10 万条固定实验才显示优势，这正是技术取舍证据。

### 10.2 local[2] 算大数据吗

回答要点：它是 Spark API 和执行模型下的单机双线程验证环境，不是多机集群。项目证明了离线数据链、分层指标、质量门和规模趋势；集群部署、百万级和容错调度仍是后续扩展，不能冒充已完成。

### 10.3 为什么不让页面直接查业务表画图

回答要点：跨表统计会加重在线库负担，且业务数据持续变化，难以复现答辩结果。固定快照和批次发布可以隔离计算、保留版本、追踪血缘并让页面稳定读取。

### 10.4 如何保证 Spark 结果正确

回答要点：不是只看 Spark 作业成功，而是检查源表计数、去重和无效行、关系错误、DWD 与 ADS 层间对账，再与独立标准库答案比较；只有质量门通过才允许发布。

### 10.5 AI 和 Spark 的关系是什么

回答要点：AI 面向个体实践提供辅助建议；Spark 面向历史事件做离线统计。AI 不负责计算事实指标，Spark 也不生成自然语言建议。两者通过已保存的业务事件衔接，但证据边界分开。

### 10.6 你做的系统防御最有价值的是什么

回答要点：不仅是参数校验，而是跨层保护，包括服务端权限过滤、状态机不变量、事务回滚、并发版本检查、幂等重放、模型调用超时与结构校验、Spark 质量失败不发布，以及浏览器网络失败时保留上一次有效批次。

### 10.7 433 个测试是否说明系统没有 Bug

回答要点：不能。它说明当前定义的 433 个场景通过；Fake 和单元测试不替代真实 MySQL、浏览器、Spark 和真实模型质量验证。测试数量也不等于覆盖率，更不等于生产可靠性。

## 11. 答辩前最终清单

- [ ] 能用 90 秒介绍项目，不堆技术名。
- [ ] 能说清 6 大技术域、31 项核心技术、36 项工程要素的计数口径。
- [ ] 能画出在线业务链、AI 链和 Spark 离线链。
- [ ] 能解释 ODS、DWD、ADS、snapshot_id、job_id、batch_id、source_cutoff。
- [ ] 能解释 90 分钟、2/4、199/200、NULL 时长这些固定样例。
- [ ] 能说明 1 万条 Spark 更慢、10 万条 Spark 更快的原因。
- [ ] 能明确 local[2] 不是多机集群。
- [ ] 能明确 AI 建议不是代码执行、教师通过或学习效果。
- [ ] 能解释 433 总测试、319 防御性下限和分层验证的区别。
- [ ] 已准备正常演示、断网演示、服务失败演示三条路线。

## 12. 本文证据边界

本轮实际执行并确认：

- 后端 433 项 unittest 全部通过。
- 前端 vue-tsc 类型检查通过。
- 前端 Vite production build 通过，保留大分包警告。
- 当前 ORM 元数据可加载 40 张表、106 个外键。

本文引用但本轮未重新执行：

- S05 真实 MySQL 发布、并发和只读 API 验证。
- S06 真实浏览器验收。
- S06 1 万 / 10 万 Spark 离线实验。
- 真实 DeepSeek 模型质量评价。

因此答辩时应说“历史验收证据显示”，不要说“今天刚刚重新跑过”。

若某文件或原理看不懂，请继续追问 AI；本文负责给学习路径、答辩路线和验收问题，不替代你自己沿源码完成一次完整调用链复盘。
