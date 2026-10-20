# ScholarHub 大数据毕业设计新版实施方案

版本日期：2026 年 10 月 16 日　适用范围：当前代码基线之后的毕业设计开发与答辩

本版以 main 的 49448de 及当前工作区为起点，重新安排 ScholarHub 的后续工作。旧方案的大数据方向继续采用：业务 MySQL 提供数据，PySpark 与 Spark SQL 完成离线处理，汇总结果通过 FastAPI 和 Vue／ECharts 展示。主要更新是把已经完成的 CR1 至 CR9 整改移出待开发清单，并按当前可信来源、事务和权限规则设计数据管道。

项目已经具备较完整的业务与验证基础，后续以真实数据处理闭环、可复现实验和论文答辩为重点。本方案中的 Spark 作业、分析结果表与离线查询接口均为拟新增内容；本版编制不直接启动这些改造。

用户已说明导师目前没有指定数据规模、必须使用的技术或提交期限。本文给出可调整的四至六周节奏，首版固定三个学习行为指标。社区、教学分析与 AI 引导式工作流按剩余时间选择，生产治理及实时计算留待后续需求明确后推进。

阅读顺序：第 1 至 3 节说明变化、现状和目标；第 4、5、8 节作为数据与接口设计依据；第 6 节按阶段执行；第 9 至 12 节组织实验、论文和答辩；附录 A 为当前全部接口，附录 B 为独立阶段开发指令。

## 1 旧方案需要如何更新

### 1.1 更新结论

需要重写现状基线、任务排序、数据来源规则和验收安排。大数据技术主线仍然成立，现有业务表和前端也继续复用。代码改动较多，主要加强了工程正确性和使用流程，并未自动形成 Spark 数据处理能力。

| 旧方案的安排 | 当前事实 | 新版处理 |
| --- | --- | --- |
| 学习进度与完成资格优先修复 | CR6A 已采用真实任务计数、计划与任务锁协调，覆盖 199／200 与并发追加 | 移为已完成；新增分析按任务明细计算，保留回归 |
| 学习记录来源按 JSON 标记识别 | CR6B 保留系统来源键，以真实 Feedback 关系决定教学来源 | 改写抽取与 DWD 来源规则，禁止直接相信 JSON.source |
| 工作流编辑保护与 Context 规则尚需加强 | CR1 至 CR3 已完善活动运行保护、后继失效和最终模型字段投影 | 保留当前机制；新增分析不修改工作流执行语义 |
| 账号缓存与异步切换存在风险 | CR4 已处理退出、账号隔离及旧响应覆盖 | 新图表复用认证与请求归属机制 |
| 教学任务与课堂操作边界需整改 | CR5、CR7、CR8 已修复 null 校验、重新核验和课堂分页 | 保留为现有能力及必要回归 |
| 完整浏览器主线待补证 | CR9 最新真实接口浏览器记录已通过 | 现有业务基线已补齐；新增分析另做端到端验收 |
| 所有接口重新规范 | 当前路径和公开字段总体保留，内部规则发生完善 | 导出最新契约、补充行为说明，避免重复实现接口 |
| Spark、ODS／DWD／ADS、离线图表待开发 | 仓库仍未发现对应依赖、作业和离线分析接口 | 作为本版核心新增工作 |
| AI 引导会话与实时计算继续扩展 | 仍属独立设计路线 | 主线稳定后选择实施，不作为数据管道前置条件 |

### 1.2 本版与旧版的关系

20261015 版保留为历史计划。本版接替其后续任务排序；其中仍适用的指标、数据权限和批次原则已重新整理。旧计划、旧 PRODUCT 描述及早期阶段报告中的状态必须结合日期判断，不能用来覆盖当前源码和 CR9 证据。

完成过的修复继续维护测试，只有后续变更破坏这些规则时才再次修改。下一步可以从范围与契约收口进入数据抽取，随后完成 Spark 处理和结果展示。

## 2 当前项目基线与可复用成果

### 2.1 架构与接口

当前技术栈为 Vue 3、TypeScript、Pinia、Axios、Element Plus、Vue Flow、ECharts，以及 FastAPI、Pydantic、SQLAlchemy、MySQL 和 AI Provider。后端仍采用 Router → Service → Repository → Model，前端通过统一 API 模块访问服务端。

本版从当前 ORM 和实际生成的 OpenAPI 核对到 34 张业务表、81 个外键约束、17 个模块、96 个路径、136 项操作。方法分布为 GET 57、POST 52、PUT 10、PATCH 4、DELETE 13。接口数量与旧版相同，表示路径集合基本稳定，不表示接口行为或内部实现没有变化。

现有业务覆盖账号与校园身份、项目与课程、计划与任务、学习记录、社区治理、工作流、个人 AI 报告、班级与教学提交反馈。Campus Studio 页面与 ECharts 组件可以复用，后续增加独立离线分析入口即可。

### 2.2 已完成的质量基础

| 当前成果 | 代码或证据位置 | 后续需要保持的规则 |
| --- | --- | --- |
| 活动工作流编辑保护与执行版本校验 | workflow、workflow_execution Repository 及 CR1 | 运行中的图不能被并发改写 |
| 节点输入、连线和后继失效规则 | Workflow Repository、Service 及 CR2 | 语义变化重算受影响后继，历史结果保留 |
| 模型字段投影与共享 Context 原子更新 | agents/base.py、project_context、CR3 | 最终消息遵循合法读取集合，跨工作流失效一致 |
| 账号隔离与最新请求生效 | 认证 client、Store、CR4 | A 的缓存、401 或旧请求不能影响 B |
| 教学任务 null 边界 | schemas/teaching.py、CR5 | 必填不能显式清空，可空字段仍允许清空 |
| 计划真实完成资格与锁协调 | repositories/learning.py、CR6A | 任务数大于零且全部完成才允许完成计划 |
| 可信教学来源与编辑保护 | LearningRecord.teaching_feedback、CR6B | 来源由 ACCEPT Feedback 关系证明，客户端不能伪造系统字段 |
| 校园重新核验与课堂分页 | campus、TeachingClassView、CR7／CR8 | 只有合法新邀请能恢复指定身份，后页内容可操作 |
| 综合业务验收 | CR9 报告与测试证据 | 新开发保留现有主线与隔离边界 |

最新已归档的 CR9 与 GitHub 交付记录包含后端 271 项测试、前端类型与构建、隔离 MySQL 主线和专项验证。CR9 的真实接口浏览器记录为 browser_mainline passed、150 次 API 请求、pageErrors 为 0，并记录测试数据清理通过。它们是当前可复用的历史验收基线，不等于新增 Spark 功能已经通过验证。

### 2.3 尚未形成的能力

当前 statistics 仍直接聚合 MySQL 业务表，个人 AI 报告仍基于服务端收集的事实快照；两者都不是 Spark 结果。依赖和业务目录中未发现 SparkSession、PySpark 作业或 ODS／DWD／ADS 管道。

自然语言生成实践流程、human_checkpoint、等待学生提交和恢复的引导会话，也不能由现有 CR 整改推断为已实现。CR 完善了原工作流基础，并没有把旧引擎自动升级为新的引导式实践系统。

## 3 毕业设计目标与范围

### 3.1 题目与研究问题

建议与导师沟通的题目为“基于 Spark 的校园学习行为分析与可视化系统设计与实现”。现有 AI 能力作为应用辅助功能；如果以后把 AI 引导写成主要研究点，再增加对应实现和质量评价。

研究问题聚焦于：业务记录如何转化为可复现的分析快照；清洗、来源识别与时间口径如何保障指标可信；离线结果如何通过权限受控的接口和图表支持学习复盘。论文的专业技术内容来自实际 Spark 程序、数据分层和实验。

### 3.2 首版完成标准

| 优先级 | 交付内容 | 完成判断 |
| --- | --- | --- |
| 必做 | 当前代码与接口基线、三个指标口径 | 状态与契约可核对，不重复列已完成整改 |
| 必做 | 白名单快照抽取、数据字典与固定小样本 | 数据来源、粒度、时区和异常规则明确 |
| 必做 | PySpark 清洗、Spark SQL 聚合及批次重跑 | 已知答案正确，相同输入结果稳定 |
| 必做 | 汇总发布、只读接口及本人分析页面 | 源样本至图表全链路可追踪 |
| 必做 | 正确性与规模实验、论文和答辩材料 | 有原始结果、解释与复现步骤 |
| 选做 | 管理员汇总、社区浏览与教学分析 | 单独明确权限、数据源和指标 |
| 选做 | AI 草案生成与分步实践引导 | 完整等待、提交、反馈及恢复闭环 |
| 后续需求 | 生产额度治理、真实试点、Kafka／Flink、集群 | 按学校要求或实际使用场景另行确定 |

达到首版标准后优先收尾论文与答辩。系统已有的社区、教学和 AI 功能继续提供场景与数据，不要求把所有模块同时扩展成新的研究方向。

## 4 新增数据管道与当前数据模型

### 4.1 目标数据流

```text
现有 Vue／FastAPI／MySQL 业务系统
→ 白名单只读抽取与一致性快照
→ ODS 批次快照
→ PySpark 清洗与关联得到 DWD
→ Spark SQL 聚合得到 ADS
→ 质量核对与受控批次发布
→ MySQL 分析结果表
→ 新增只读 API
→ Vue／ECharts 分析页面
```

离线作业与 Web 服务分开。图表 GET 查询读取已发布结果，不现场启动 Spark。原 /statistics 接口保持现有业务聚合含义，新接口显示数据集、批次、截止时间和规则版本。

### 4.2 核心数据源与可信来源

| 数据源 | 首版使用的字段或关系 | 当前限制 |
| --- | --- | --- |
| learning_records | id、user_id、关联 ID、record_type、duration_minutes、occurred_at、created_at | 记录可编辑删除，没有 updated_at；分钟由用户填写 |
| daily_tasks | id、user_id、plan_id、project_id、status、scheduled_date、completed_at | 当前状态快照，不是完整状态事件流 |
| feedback | learning_record_id、decision、必要关联 ID | 仅为可信教学来源关联，不抽取评阅正文 |
| projects／learning_plans | ID、所有者、必要关联与状态 | 作为关系维度，不能用展示进度代替任务计数 |
| project_views 选做 | id、project_id、user_id、viewed_at | 已记录社区详情浏览，刷新重试可能增加 PV |
| submissions／submission_versions 选做 | 班级、任务、学生成员、截止快照、版本、提交时间 | 只记录成功落库版本，正常接口拒绝逾期提交 |

CR6B 后，分析不能仅用 record_metadata.source 判断“教学生成”。抽取时通过 feedback.learning_record_id 连接记录，且 decision 为 ACCEPT，才派生可信教学来源；其他记录按普通记录或明确异常分类。历史 JSON 即使写有 source，也不能单独成为来源证明。

新建和修改接口禁止客户端提交 source、submission_id、version_number 等系统保留键。来源字段的输出由服务端依据真实关系生成。DWD 应复用同一含义，只导出必要关联事实，不把整个 JSON 或评阅内容带入数据集。

### 4.3 ODS 与更新策略

第一版按统计窗口抽取完整快照，不使用最大 ID 或 created_at 假装捕获修改删除。一次受控只读一致性事务取得所需字段后尽快结束，Spark 清洗和模型调用均在该事务之外。多个独立 JDBC 连接不能自动视为同一快照。

每批保存 batch_id、dataset_kind、统计窗口、timezone、source_cutoff、抽取时间、源行数和 metric_version。固定快照保持不可变，用于复算和实验。初始抽取可使用明确字段的 CSV，再由独立数据环境转换为 Parquet；所有文件均使用显式 schema。

不抽取密码、Token、邮箱、邀请凭证、完整项目正文、代码或 AI 提示词。性能合成数据直接生成独立文件，与演示业务快照分开。真实库写入及迁移在实施阶段明确目标与授权，不沿用历史测试库名称作为自动写入依据。

### 4.4 DWD 与质量规则

核心明细为学习记录事实和任务批次快照，教学来源为关系派生字段。按源主键去重：相同内容重复可以去除，同主键冲突内容进入异常记录，不能任意留一条。字段类型、状态、时间、关联和分钟范围均有明确规则。

教学自动记录可有 NULL 时长，保留缺失数，不补成真实学习分钟。当前记录 API 的分钟范围为 1 至 1440 或 NULL，而数据库允许历史零值；零、NULL 和不符合当前 API 范围的数据在字典中单独定义处理方式，不能混为同一种缺失。

DATETIME 沿用 UTC 存储，按 Asia/Shanghai 归属业务日；查询采用本地起始日零点到结束日次日零点的左闭右开窗口，再转换为 UTC。scheduled_date 是 DATE，直接作为计划日期，不再次转换时区。

质量报告记录源行数、去重后行数、有效数、异常数及原因；总数关系能够核对，样本能定位回源主键。按记录统计，不因用户或项目关联缺失就默默丢弃已存在的分钟。

### 4.5 ADS 与批次发布

核心版先设计批次元数据和用户日汇总两类结果表，拟名 analytics_batches、analytics_learning_daily。后者按 batch_id、user_id、biz_date 唯一，保存记录数量、分钟、缺失数、来源分类及任务各状态计数。新增表和索引在 D3 实施前核定，保持业务表原职责。

汇总先写未发布批次，经质量核对后在短事务内标记 completed；查询只读取已完成批次。已发布汇总禁止覆盖，同输入重试复用结果，需要重算时创建新批次；只有未发布批次可以清理并重写自己的暂存与结果。

前端一次选定 batch_id，所有图表固定使用该批次。发布失败时继续提供上一成功结果，并明确其截止时间。普通用户只能读取授权的本人批次与行；管理员总体和教师班级分析作为选做单独设计。

## 5 核心指标与数据权限

### 5.1 首版三个指标

| 指标 | 口径 | 展示规则 |
| --- | --- | --- |
| 已记录学习分钟 | 按 occurred_at 业务日求和非 NULL 的 duration_minutes | 同时显示记录数与缺失数，说明属于记录值 |
| 记录活跃天数及来源 | 本人周期内去重存在学习记录的 biz_date，按普通／可信教学来源拆分 | 不解释为登录活跃、停留时长或真实专注时长 |
| 按计划日期任务完成率 | completed 数／该 scheduled_date 下全部保留任务数 | 保存分子分母和取消数，分母为零显示无样本 |

第三项沿用现有报告包含 cancelled 的分母。例如 4 个保留任务中完成 2 个、进行中 1 个、取消 1 个，完成率为 2／4。以后如需排除取消任务，使用新的 metric_version，同步文档和图表。

CR6A 已修正“百分比四舍五入等于 100 就允许完成计划”的问题。分析同样必须使用任务分子分母：199／200 是 99.5%，不能凭计划展示字段为 100 推断全部完成；空计划不能解释为已完成。任务 completed_at 和 scheduled_date 分别代表完成时间和计划日期，按不同问题使用。

### 5.2 选做指标与限制

管理员总体汇总可增加有记录用户数，定义为业务日内去重 user_id。首页专注计时、登录频次、匿名访客和 API 请求成功率，需要相应的服务端事件记录，不能从界面、提交表或当前记录数量倒推出结论。

社区可统计已记录 project_views 的 PV 与账号 UV。教学可统计首版提交提前量，即截止快照减首版 submitted_at 的分钟数，展示分布、样本数和缺失数；正常 API 拒绝逾期提交，因此首版按时率通常为 100% 或无样本，只适合核验截止规则。

技术栈数量可保留现状；现有前 N 项百分比不直接当作全量占比引用。若扩展技术栈趋势、工作流成功率或 AI 用量，先定义分母、时间字段、NULL 和数据覆盖，再新增指标，不把未记录用量当成零。

### 5.3 权限与页面

首版优先做本人分析页，复用现有 ECharts 和 Campus Studio 样式，显示批次、统计周期、来源、截止时间、完成时间和口径版本。页面包含分钟趋势、记录活跃与来源、任务状态和完成率，支持日期选择、空结果与失败提示。

普通账号只看本人汇总；同班教师的权限限于当前授权的教学任务分析；管理员总体是明确授权的汇总。learning_records 和 daily_tasks 没有 class_id，不能把班级关系当作读取所有个人学习数据的授权。

合成数据只用于独立规模实验；如果增加实验展示，提供受控汇总并明确 synthetic 标记，不能混入个人历史或声称有真实用户规模。

## 6 新版分阶段实施安排

### D0 固定新基线与契约

建议半天至一天。以本版为入口确认题目、三个指标和最小演示；导出当前 OpenAPI，整理接口模块、角色范围与 CR 行为变化。把 CR1 至 CR9 列为已完成回归基线，不再作为首批功能开发。

收口现有错误文档：实际 error.code／message／request_id 与 OpenAPI 的 422 描述仍不一致。先给出兼容说明、接口文档和必要契约样本；改变公开返回字段时单独确认。同步过时的 PRODUCT、知识网络或论文描述，但保留历史报告原日期和原结论。

交付物：范围页、需求到实现与验证矩阵、指标卡、接口契约基线。验收：当前能力、拟新增能力和选做清楚；每项核心要求有完成依据。

### D1 环境与小样本快照

建议两至三天。核对 Python、JDK、内存与磁盘，选择并固定可验证的 Spark 版本，在独立数据环境完成最小 CSV／Parquet 读写与聚合。新增依赖先给具体版本及影响，不改变后端已有虚拟环境。

实现学习记录、任务和必要 Feedback 事实的白名单抽取；固定小样本与手算答案，覆盖普通记录、真实教学关系、历史伪 JSON、NULL、零、跨午夜、取消和空任务。定义数据字典、snapshot 与目录规则，再形成 ODS。

交付物：环境说明、抽取入口、快照、元信息和预期结果。验收：记录分钟和来源均可核对；输入不包含秘密或无关正文；快照能够稳定复用。

### D2 PySpark 与 Spark SQL

建议三至五天。按第 4、5 节实现显式 schema、来源关系、去重、异常分流与日期转换。DataFrame 负责规范明细，Spark SQL 负责三个指标的聚合；输出 DWD、ADS 和质量计数。

先与手算答案比较，再验证同快照与规则重跑得到相同结果。保留作业参数、退出状态和失败原因，入口可以通过命令行复现，不只保留 Notebook 截图。

交付物：清洗与聚合作业、异常样本、指标结果与规则测试。验收：所有已知答案正确；199／200、可信来源、NULL 和无样本规则保持准确。

### D3 汇总发布与系统展示

建议三至五天。先审查新增结果表、增量迁移、批次发布和只读接口，再按确认后的设计实施。只写分析汇总，不覆盖现有学习记录、工作流结果或 AI 报告。

增加本人离线分析页面，API 从认证上下文确定 user_id，不能接受任意用户 ID。前端复用 CR4 的账号切换、请求归属和最新响应处理，日期切换时避免旧批次覆盖新结果。

交付物：迁移与回退说明、导入发布入口、接口契约和页面。验收：固定样本能追踪至 MySQL、API 和图表；失败不发布半批次；跨用户拒绝；退出与切换账号不泄漏汇总。

### D4 实验与回归

建议三至五天。小样本做正确性；固定种子生成两至三档合成文件做规模实验。候选一万、十万、一百万条，按本机能力试跑后选定实际规模，记录真实行数、分布和输出。

固定输入与指标规则，与 Python 标准库实现或受控 MySQL 结果比较。先比较答案，再测量耗时；区分抽取、Spark 启动、清洗、聚合、发布和端到端时间，预热后至少测量三次，记录原始值、中位数与范围。

在专用测试环境补做新分析的真实 API 与页面主线，并按变更影响运行相关 CR 回归。现有 CR9 验收证明原业务，新分析仍需自己的证据。数据写入前核对明确目标和空库状态，测试清理只处理本次资源。

交付物：实验环境、生成规则、原始测量、分析图和回归记录。验收：同口径、可复现、不挑选结果；合成与真实数据分开；失败、越权、重跑及清理均有结果。

### D5 论文与答辩

建议三至四天，从 D0 起同步积累材料。围绕已完成的数据链路、关键代码、实验和权限说明撰写论文，统一数据字典、接口、图表标签和论文章节。

冻结一套演示样本与成功批次，准备十分钟脚本、截图或视频和失败恢复案例。使用 CR9 的原业务证据作为基础，新增 Spark 与图表证据作为本次专业主线；不能把 Fake Provider 当作真实模型质量结论。

交付物：论文、PPT、演示材料、关键代码导读和导师问答。验收：本人能从一条记录解释到指标、批次、接口和图表，也能解释何处使用 AI、何处由确定性规则验证。

## 7 代码与全部接口的规范方法

### 7.1 现有接口如何维护

附录 A 列出当前全部 136 项操作。按模块补齐契约卡，记录用途、调用页面、方法与路径、请求与响应 Schema、真实错误、资源归属、分页、排序、时间、版本、幂等及验证用例。公开握手、个人资源、校园教学和治理接口均在范围内。

接口数量不变时也要更新行为说明，尤其是工作流活动运行保护、CR5 显式 null、CR6 保留来源字段、CR7 新邀请恢复规则和 CR8 分页。现有 PUT 的部分更新约定如实说明，避免为风格统一批量改成 PATCH。

现有错误返回与 OpenAPI 应保持一致，401／403／404／409／422 等按真实实现描述。字段错误位置可作为后续兼容改进，避免在本轮文档任务中默认实施新的公开返回结构。

### 7.2 一个应能讲清的现有接口

POST /api/v1/learning/tasks/{task_id}/complete 通过当前用户与所有权校验，检查任务和计划状态，使用当前计划与任务状态更新完成数量和进度，再返回任务 DTO。重复完成已完成任务不增加次数；它不会自动生成一条手工学习记录。计划完成另外检查真实 total 大于零且 completed 等于 total，不能用四舍五入后的 progress 代替。

新增分析接口也要达到这种可解释程度：数据来自哪个批次、按哪个时间统计、谁能查询、分母为什么这样选、失败怎样表示，都能回到具体代码和测试。

### 7.3 新代码与冗余控制

前端保持页面组合、API 适配与 Store 状态的职责，复用已有组件与领域函数；不要在多个页面各算一遍统计分母。数据管道独立组织 extract、transform、aggregate、load 和 tests，按当前阶段创建所需目录，不构建通用 ETL 平台。

服务端继续用 Schema 校验、Service 授权与业务规则、Repository 查询。复用 CR 已建立的锁顺序和短事务约定，避免为分析读取重新引入模型等待期间的事务。工作流路径的事务改善不能自动推断为所有独立 Agent 和学习报告路径都已改完；这些次要改进在有具体影响时单独处理。

现有学习进度查询已复用任务计数，旧计划所列重复计算要重新按调用关系判断。只清理有证据无用的代码，不删除历史提交、快照或审计，也不按固定行数机械拆模块。

## 8 新增数据库与分析接口草案

### 8.1 最小数据结构

analytics_batches 记录窗口、时区、dataset_kind、source_cutoff、metric_version、状态、质量数量和耗时；analytics_learning_daily 保存本人日粒度结果及任务分子分母。两类表为拟议结构，具体类型、唯一键和索引在 D3 形成可审查设计。

按批次和 user_id、biz_date 查询设置必要索引；比例由已保存的分子分母计算。数据库验收既核对新增表的名称，也核对类型、可空性、默认值、唯一约束与索引列，避免仅凭同名约束判断迁移正确。版本、快照和原有 34 张表继续保留。

### 8.2 拟议只读契约

下列接口尚未实现，属于 D3 设计草案；新增公共 API 和数据结构的影响在实施前确认。

| 拟议方法与路径 | 用途与范围 | 关键返回 |
| --- | --- | --- |
| GET /api/v1/analytics/offline/batches | 本人可用完成批次；总体批次需明确权限 | 批次、窗口、来源、截止时间、规则版本 |
| GET /api/v1/analytics/offline/me/daily | 本人日汇总，user_id 由认证决定 | 分钟、缺失数、来源、任务分子分母 |
| GET /api/v1/analytics/offline/admin/overview | 选做；管理员授权总体汇总 | 有记录用户数、分钟、任务与质量数量 |
| GET /api/v1/analytics/offline/classes/{class_id}/assignments | 选做；当前同班教师任务分析 | 提交提前量、样本和缺失数 |

参数包含 batch_id、起止日和有界分页。响应带 dataset_kind、timezone、source_cutoff、metric_version；无可用批次与空列表分别表达，分母为零返回 NULL 并显示无样本。服务端验证批次范围与窗口，不允许拼接任意文件路径或读取任意用户结果。

第一版通过受控 CLI 发起作业。没有实际使用需要时，不新增 HTTP 作业启动、任意代码执行或复杂调度能力。

## 9 实验与验证设计

### 9.1 正确性矩阵

| 场景 | 应验证的结果 |
| --- | --- |
| 普通记录与真实教学来源 | 仅 ACCEPT Feedback 关系派生教学来源，分钟与 NULL 分开 |
| 历史伪造 JSON 来源 | 不被认定为教学通过记录 |
| UTC 午夜与业务 DATE | 日期归属正确，scheduled_date 不发生二次偏移 |
| 199／200 与空计划 | 分子分母准确，不把展示整数当完成资格 |
| 取消、无记录与无样本 | 分母和状态拆分清楚，NULL 不变成成功率零 |
| 源记录修改或删除 | 新快照重算反映变化，旧批次保持可追溯 |
| 重复主键与冲突内容 | 相同重复可去重，冲突有明确异常原因 |
| 发布失败、重试与重算 | 不覆盖已完成批次，不展示半成品 |
| 账号和日期快速切换 | 没有旧数据泄漏或陈旧响应覆盖 |
| 个人与跨班访问 | 本人可读，越权拒绝，教师不读取私人学习全量 |

### 9.2 规模与性能

采用单机 local 模式先完成实验，建议固定如 local[2] 的线程设置并记录实际参数。数据量按本机试跑确定，固定种子、用户数、日期跨度、异常比例与分区。百万条候选样本不等于必须把百万条记录写入业务库。

对照实现使用同一快照、同一过滤、NULL、来源和分母规则，分别统计计算耗时与全流程耗时；使用 MySQL 对照时说明输入载入成本。小数据下 Spark 启动可能占较大比例，以实测解释性能，不预设更快。可选记录 explain、任务阶段与 shuffle，帮助说明瓶颈。

每组保留至少三次预热后测量，报告中位数、范围、输出行数和异常。单机并行实验只说明本机环境，集群扩展能力作为展望；合成规模也不当作真实师生使用规模。

### 9.3 验证工具与证据

已有 unittest、CR 专项、verify_integration.py 与真实浏览器主线继续作为基础。新增管道先测试纯清洗与小样本聚合，再测试结果发布和新 API；共享认证或前端状态发生变化时补跑相应 CR4 场景，工作流未改则不盲目重写其测试。

前端沿用 pnpm typecheck、pnpm build；后端运行与变更有关的 unittest 及必要依赖检查。仓库没有独立 Lint／格式化／安全扫描命令时如实记录，不安装一整套工具来满足形式。历史构建的 Analytics 大包提示按实际影响处理，不作为阻止 Spark 开发的前置任务。

每次保存输入批次、命令参数、软件环境、实际结果与必要截图。API、页面、计算正确性、真实模型质量和课堂使用效果分开验证。历史失败日志保留，最终结论指向对应成功复验。

## 10 AI 与其他后续路线

### 10.1 现有 AI 能力继续复用

已有 Agent、Context、工作流记录和 AI 报告可用于演示应用价值。CR 已完善字段读取和图运行一致性，新增离线分析不应反向修改这些约定。AI 可解释学习数据，但核心指标由确定性规则产生，保存生成时输入事实。

完整 AI 引导方案继续按 W0 场景与契约、W1 草案生成、W2 等待提交与分步调用、W3 成果落实、W4 质量评价推进。若选择实施，先用固定 CSV 清洗练习，保留旧 DAG 模式，独立设计引导会话、尝试版本与恢复；只有生成画布不能算完整引导。

### 10.2 本次毕业交付之后

社区浏览、教学提交提前量可在核心指标稳定后加入。平台额度治理、公开部署、隐私与真实课堂试点在具体使用条件下分别推进。AI 测试入口向非受控账号开放前应收紧；独立 Agent 和报告调用的连接占用按实际风险收尾，不把它扩展成整套生产平台改造。

Kafka／Flink 需要明确的事件采集、重放、延迟与一致性实验，待离线主线完成后再决定。Hadoop 集群、复杂调度、任意学生代码执行和自动判题均不进入核心版。

## 11 论文与答辩材料

### 11.1 章节与证据

| 章节 | 核心内容与应有材料 |
| --- | --- |
| 绪论与技术背景 | 问题、范围、相关研究，Spark 与数据处理方法 |
| 需求与总体设计 | 需求矩阵、角色权限、现有业务与新增管道边界 |
| 数据与指标设计 | 源字段、可信关系、分层、时间、NULL 和分母 |
| 数据处理实现 | 抽取、DataFrame、Spark SQL、异常与批次发布 |
| 系统展示与接口 | 结果表、新 API、前端图表及原业务复用 |
| 测试与实验 | 已知答案、规模、性能、越权、失败恢复与回归 |
| 总结与展望 | 实际完成范围、单机局限、选做与实时扩展 |

至少准备总体数据流、核心 ER、分析表关系、批次发布时序、指标字典、权限矩阵和实验结果图。代码整改作为工程质量与关键设计证据使用，不把缺陷数量当作研究创新指标。

### 11.2 十分钟演示

第一分钟介绍场景与目标；第二分钟展示记录、任务和可信教学来源；第三至第五分钟展示固定快照、异常处理和 Spark 聚合；第六至第七分钟从批次、API 到图表核对结果；第八分钟解释规模实验；第九分钟展示失败或越权处理；第十分钟说明结论与后续工作。

演示准备固定小样本与已完成批次，Spark 全流程保留可复现命令和备用录屏。现场能讲解 learning 真实计数、Feedback 来源、抽取、清洗、SQL、发布和查询七处关键代码即可，不需要逐项展示全部 136 个接口。

### 11.3 导师常见问题

| 问题 | 回答依据 |
| --- | --- |
| 这次改了很多，新增了什么大数据能力 | CR 是业务质量基础；以实际完成的 Spark 管道和实验回答新增部分 |
| 为什么同时保留 MySQL 和 Spark | MySQL 服务事务与图表查询，Spark 处理批量清洗、关联和聚合 |
| 为什么不直接把 progress 当完成率 | 展示整数会四舍五入，199／200 与真实全部完成不同 |
| 教学记录如何保证来源可信 | 展示 Feedback.learning_record_id 和 ACCEPT 关系，客户端来源键受限 |
| 分钟是否等于真实学习时间 | 是已记录分钟，NULL、来源与数据采集边界明示 |
| 为什么不直接按最大 ID 增量 | 记录可修改删除且无 updated_at，首版采用窗口完整快照 |
| 重跑或失败会不会改坏历史图表 | 不可变输入、完成批次不覆盖、失败保留上一成功结果 |
| Spark 是否更快、数据是否真实 | 出示同口径测量、单机参数及真实／合成数据区分 |
| 原系统有没有被破坏 | 说明既有契约、CR9 基线与新增后的相关回归 |
| 本人做了什么、AI 做了什么 | 按真实记录解释需求、设计、实现、验收和辅助工具，能独立讲关键代码 |

## 12 时间安排与每阶段停止条件

建议预留四至六周，按已有资料与学习速度调整：第一周完成 D0、D1；第二周 D2；第三周 D3；第四周 D4；随后完成 D5 与论文修改。论文资料从第一周同步积累，不把全部写作留到最后。

时间紧时保留三个核心指标、本人页面、固定样本、两档规模实验和完整答辩主线，减少选做。时间充足时选择一个扩展，不同时启动 AI 引导、实时计算和生产部署。

| 阶段 | 进入下一阶段的条件 |
| --- | --- |
| D0 | 范围、指标、权限与接口基线一致 |
| D1 | 环境最小作业通过，数据样本与预期答案固定 |
| D2 | 三指标与答案一致，同输入重跑稳定 |
| D3 | 发布、API、页面与跨用户隔离闭环 |
| D4 | 原始实验、正确性、回归和清理证据完整 |
| D5 | 论文、演示与代码讲解采用同一事实和口径 |

后续阶段需要依赖、API 或数据结构变更时，先形成具体设计和兼容说明再确认实施。当前文档交付不等于已批准所有未来迁移或写库操作。

## 13 执行清单与资料维护

近期顺序为：固定本版基线与三个指标；补接口和旧描述；准备独立数据环境与小样本；实现 Spark；接入本人图表；完成实验；收尾论文。CR1 至 CR9 只作为保持通过的回归集合。

最终交付应有范围页、需求矩阵、数据字典、当前接口目录与契约卡、可运行管道、固定快照与预期答案、质量报告、批次结果、新 API、页面、实验原始值、论文、PPT、演示和关键代码说明。

R0 对应 D0；R1 在全过程积累；R2 复用 CR9 原业务主线并补新增分析；R3A 对应 D4；R3B 随真实模型评价选做；R4、R5 在 D5 收尾。L1 至 L3 与 CR6 的当前实现保留；旧 L4 缺口已由最新主线证据补齐；L5 统计口径和 L6 调试入口仍按实际用途安排。

现状依据：当前源码与 OpenAPI；20261016-CR9-严格审查整改最终验收报告；CR9 的 07-live-browser-retest.log；20261016-GitHub检查与推送报告；CR1 至 CR8 阶段报告。旧 20261015 计划用于版本对照，不覆盖新版待办。

技术参考：[Spark 固定版本安装说明](https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html)、[Spark Parquet 数据源](https://spark.apache.org/docs/4.0.1/sql-data-sources-parquet.html)。实施时按最终固定版本核对 Python／Java 兼容与实际运行；引用这些文档不表示本机数据环境已经安装。

## 附录 A 当前全部接口清单

以下由本版编制时实际生成的 OpenAPI 提取，共 17 个模块、96 个路径、136 项操作。路径统一省略 /api/v1；详细字段以对应 Schema 和 /docs 为准，实际业务授权以 Service 为准。第 8 节拟新增接口不计入现有目录。

### 服务状态 health

1 个路径，1 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /health | 服务健康检查 |

### 认证 auth

7 个路径，7 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /auth/slider/challenge | 获取一次性滑块挑战 |
| POST | /auth/slider/verify | 校验滑块并签发一次性登录凭证 |
| POST | /auth/register | 注册用户 |
| POST | /auth/login | 用户登录 |
| POST | /auth/change-password | 修改当前账号密码 |
| POST | /auth/logout-all | 撤销当前账号全部会话 |
| POST | /auth/reset-password | 使用一次性凭证重置密码 |

### 校园身份 campus

9 个路径，9 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /campus/me | 获取本人校园身份 |
| POST | /campus/invitations | 签发校园邀请 |
| POST | /campus/invitations/redeem | 兑换本人校园邀请 |
| GET | /campus/admin/accounts | 查询校园账号 |
| PATCH | /campus/admin/accounts/{user_id} | 变更账号或校园身份 |
| GET | /campus/admin/invitations | 查询校园邀请 |
| POST | /campus/admin/invitations/{invitation_id}/revoke | 撤销校园邀请 |
| POST | /campus/admin/accounts/{user_id}/password-resets | 签发一次性密码重置凭证 |
| GET | /campus/admin/audits | 查询账号管理审计 |

### 教学班与任务 campus-teaching

9 个路径，14 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /campus/classes | 查询可访问的教学班 |
| POST | /campus/classes | 教师创建教学班 |
| GET | /campus/classes/{class_id} | 获取教学班详情 |
| PATCH | /campus/classes/{class_id} | 编辑或归档教学班 |
| GET | /campus/classes/{class_id}/members | 查询教学班成员 |
| POST | /campus/classes/{class_id}/members | 增加教学班成员 |
| PATCH | /campus/classes/{class_id}/members/{member_id} | 退出或移除教学班成员 |
| GET | /campus/classes/{class_id}/assignments | 查询教学班任务 |
| POST | /campus/classes/{class_id}/assignments | 创建教学任务草稿 |
| GET | /campus/assignments/{assignment_id} | 获取教学任务详情 |
| PATCH | /campus/assignments/{assignment_id} | 修改教学任务 |
| POST | /campus/assignments/{assignment_id}/publish | 发布教学任务 |
| POST | /campus/assignments/{assignment_id}/close | 关闭教学任务 |
| POST | /campus/assignments/{assignment_id}/archive | 归档教学任务 |

### 成果提交与反馈 campus-submissions

9 个路径，10 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /campus/assignments/{assignment_id}/submissions | 提交成果或追加版本 |
| GET | /campus/assignments/{assignment_id}/submissions | 查询指定任务的提交 |
| GET | /campus/submissions | 查询本人提交或教师待评列表 |
| GET | /campus/submissions/pending-assignments | 查询学生待提交或待修改任务 |
| GET | /campus/submissions/{submission_id} | 获取提交详情 |
| GET | /campus/submissions/{submission_id}/versions | 分页查询提交版本历史 |
| POST | /campus/submissions/{submission_id}/versions/{version_number}/feedback | 教师退回或确认通过指定版本 |
| DELETE | /campus/submissions/{submission_id}/versions/{version_number}/project-reference | 本人解除提交版本的项目来源关联 |
| GET | /notifications | 查询本人站内通知 |
| POST | /notifications/{notification_id}/read | 标记本人通知为已读 |

### 当前用户 users

1 个路径，1 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /users/me | 获取当前用户 |

### 个人项目 projects

2 个路径，5 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /projects | 获取当前用户的项目列表 |
| POST | /projects | 创建项目 |
| GET | /projects/{project_id} | 获取项目详情 |
| PUT | /projects/{project_id} | 更新项目 |
| DELETE | /projects/{project_id} | 删除项目 |

### 项目上下文 project-context

3 个路径，5 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /projects/{project_id}/context | 从项目创建 ProjectContext |
| GET | /projects/{project_id}/context | 读取 ProjectContext |
| PUT | /projects/{project_id}/context | 更新 ProjectContext 并标记依赖节点过期 |
| POST | /workflows/{workflow_id}/nodes/{node_id}/context/read | 按节点权限读取 ProjectContext |
| POST | /workflows/{workflow_id}/nodes/{node_id}/context/write | 按节点权限写入 ProjectContext |

### 平台统计 statistics

4 个路径，4 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /statistics/today | 查询今日平台统计 |
| GET | /statistics/trend | 查询平台趋势 |
| GET | /statistics/projects | 查询项目统计 |
| GET | /statistics/tech-stacks | 查询技术栈统计 |

### 社区与治理 community

19 个路径，23 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /community/projects | 浏览校园社区项目 |
| GET | /community/projects/{project_id} | 获取社区项目详情 |
| GET | /community/tags | 获取社区项目标签 |
| POST | /projects/{project_id}/publication-requests | 申请发布或更新社区作品 |
| GET | /projects/{project_id}/publication | 查询本人项目发布进度 |
| GET | /community/publications/mine | 查询本人发布申请 |
| POST | /community/publications/{publication_id}/withdraw | 撤回社区发布 |
| GET | /community/moderation/publications | 查询待审核社区作品 |
| POST | /community/moderation/publications/{publication_id}/decisions | 审核或下架社区作品 |
| POST | /community/reports | 举报社区项目或评论 |
| GET | /community/governance/cases | 查询本人相关或管理员待处理案件 |
| POST | /community/moderation/actions/{action_id}/appeals | 对下架或隐藏动作申请复核 |
| POST | /community/moderation/cases/{case_id}/decisions | 处理举报或复核 |
| POST | /projects/{project_id}/publish | 旧发布入口 |
| DELETE | /projects/{project_id}/publish | 兼容撤回社区项目 |
| POST | /projects/{project_id}/view | 记录项目浏览 |
| GET | /projects/{project_id}/comments | 获取项目评论 |
| POST | /projects/{project_id}/comments | 发表评论 |
| DELETE | /comments/{comment_id} | 删除自己的评论 |
| POST | /projects/{project_id}/like | 点赞项目 |
| DELETE | /projects/{project_id}/like | 取消点赞项目 |
| POST | /projects/{project_id}/favorite | 收藏项目 |
| DELETE | /projects/{project_id}/favorite | 取消收藏项目 |

### 个人工作台 workspace

6 个路径，8 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /workspace/dashboard | 获取个人工作台聚合数据 |
| GET | /workspace/tasks | 获取个人任务 |
| POST | /workspace/tasks | 创建个人任务 |
| POST | /workspace/tasks/{task_id}/complete | 完成个人任务 |
| GET | /workspace/projects | 获取工作台项目进度 |
| GET | /workspace/projects/{project_id} | 获取工作台项目详情 |
| GET | /workspace/records | 获取个人学习记录 |
| POST | /workspace/records | 保存学习记录 |

### 课程 courses

2 个路径，5 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /courses | 获取我的课程 |
| POST | /courses | 创建课程 |
| GET | /courses/{course_id} | 获取课程详情 |
| PUT | /courses/{course_id} | 更新课程 |
| DELETE | /courses/{course_id} | Delete Course |

### 学习管理 learning

7 个路径，16 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /learning/plans | 获取学习计划列表 |
| POST | /learning/plans | 创建学习计划 |
| GET | /learning/plans/{plan_id} | 获取学习计划详情 |
| PUT | /learning/plans/{plan_id} | 更新学习计划 |
| DELETE | /learning/plans/{plan_id} | 删除学习计划 |
| GET | /learning/tasks | 获取每日任务列表 |
| POST | /learning/tasks | 创建每日任务 |
| GET | /learning/tasks/{task_id} | 获取任务详情 |
| PUT | /learning/tasks/{task_id} | 更新每日任务 |
| DELETE | /learning/tasks/{task_id} | 删除每日任务 |
| POST | /learning/tasks/{task_id}/complete | 完成每日任务 |
| GET | /learning/records | 获取学习记录列表 |
| POST | /learning/records | 创建学习记录 |
| GET | /learning/records/{record_id} | 获取学习记录详情 |
| PUT | /learning/records/{record_id} | 更新学习记录 |
| DELETE | /learning/records/{record_id} | 删除学习记录 |

### 个人学习报告 learning-reports

2 个路径，3 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /learning-reports | 生成当前用户的 AI 学习报告 |
| GET | /learning-reports | 查询学习报告列表 |
| GET | /learning-reports/{report_id} | 查询学习报告详情 |

### 工作流 workflows

10 个路径，20 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /workflows | 获取当前用户的工作流列表 |
| POST | /workflows | 创建工作流 |
| POST | /workflows/{workflow_id}/run | 运行或重新生成工作流 |
| GET | /workflows/{workflow_id}/runs | 获取 WorkflowRun 列表 |
| GET | /workflows/{workflow_id}/runs/{run_id} | 获取 WorkflowRun 详情和节点结果 |
| GET | /workflows/{workflow_id}/graph | 读取完整工作流图 |
| PUT | /workflows/{workflow_id}/graph | 原子保存完整工作流图 |
| GET | /workflows/{workflow_id}/nodes | 获取工作流节点列表 |
| POST | /workflows/{workflow_id}/nodes | 创建工作流节点 |
| GET | /workflows/{workflow_id}/nodes/{node_id} | 获取工作流节点详情 |
| PUT | /workflows/{workflow_id}/nodes/{node_id} | 更新工作流节点 |
| DELETE | /workflows/{workflow_id}/nodes/{node_id} | 删除工作流节点 |
| GET | /workflows/{workflow_id}/edges | 获取工作流边列表 |
| POST | /workflows/{workflow_id}/edges | 创建工作流边 |
| GET | /workflows/{workflow_id}/edges/{edge_id} | 获取工作流边详情 |
| PUT | /workflows/{workflow_id}/edges/{edge_id} | 更新工作流边 |
| DELETE | /workflows/{workflow_id}/edges/{edge_id} | 删除工作流边 |
| GET | /workflows/{workflow_id} | 获取工作流详情 |
| PUT | /workflows/{workflow_id} | 更新工作流 |
| DELETE | /workflows/{workflow_id} | 删除工作流 |

### AI 调试 ai

1 个路径，1 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /ai/test | 测试统一 AI Provider |

### Agent agents

4 个路径，4 项操作。路径省略统一前缀 /api/v1。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | /agents/project-analysis | 运行项目分析 Agent |
| POST | /agents/prompt | 运行开发 Prompt Agent |
| POST | /agents/project-review | 运行项目审查 Agent |
| GET | /agents/results/{request_id} | 查询当前用户的 Agent 结果 |


## 附录 B 独立阶段开发指令

### D0 指令

依据本版方案和当前工作区整理题目、范围、三个指标、权限和接口契约。先核对 CR1 至 CR9 的当前实现与证据，把已完成事项移出待开发。导出 OpenAPI 并列出旧描述和错误契约的最小修改，保留所有已有路径与字段；需要改变公开返回时先给兼容方案，不批量改名或重构。交付范围页、指标卡与规范收口清单。

### D1 指令

只做独立数据环境与固定小样本。先检查并提出可验证的 Python／JDK／Spark 版本方案，确认新增依赖后再安装。抽取 learning_records、daily_tasks 与必要 Feedback 事实，可信来源依据 ACCEPT 关系，不相信任意 JSON.source。保持 UTC、DATE、NULL 与历史零值的差异，采用窗口快照，不向业务库灌入大规模数据。交付数据字典、快照、元信息与正确答案。

### D2 指令

只实现三个核心指标的 PySpark 清洗与 Spark SQL 聚合。用显式 schema 处理去重、冲突、来源、时间和异常；先核对固定答案，覆盖 199／200、取消、空任务、NULL 和历史伪来源，再验证同输入重跑一致。输出 DWD、ADS、质量计数、参数和结果，不扩展实时平台或工作流执行语义。

### D3 指令

先给结果表、增量迁移、发布机制和只读 API 的具体设计，取得对应变更确认后实施。完成批次不能覆盖；失败保留旧结果；本人查询由认证确定 user_id。复用现有账号隔离与最新请求机制，保留原 statistics 和 CR 行为。交付发布入口、契约、页面及真实查询、越权和切换场景证据。

### D4 指令

先固定环境、数据规模、种子、分布、测量阶段和对照规则，再生成独立合成文件。先验证答案，再按同一口径测量，至少保存三次预热后原始结果，不预设 Spark 更快。新分析端到端测试使用明确确认的专用环境；相关 CR 按变更影响回归。交付原始数据、分析图、复现命令和清理结果。

### D5 指令

只依据实际完成阶段整理论文、PPT、演示和关键代码导读。统一指标、接口、批次和实验数字；以新 Spark 数据链路为主，原业务与 CR 作为复用基础。准备导师问答、固定案例和录屏，区分 AI 建议、结构校验、真实运行和人工核对，未实现能力放入后续计划。
