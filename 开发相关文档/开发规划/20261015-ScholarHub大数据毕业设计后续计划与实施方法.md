# ScholarHub 大数据毕业设计后续计划与实施方法

编制日期：2026 年 10 月 15 日　适用对象：项目开发者与毕业设计指导教师

本计划把 ScholarHub 从已有的 AI 辅助校园学习与代码实践系统，发展为包含实际 Spark 离线处理能力的学习行为分析系统。保留 Vue 3、FastAPI 和 MySQL，以“业务产生数据-抽取快照-Spark 清洗与计算-汇总结果入库-接口查询-图表解释-实验验证”为毕业设计主线。代码与接口规范服务于可维护、可复现和可答辩的交付。

用户已确认导师目前没有指定数据规模、必须使用的技术或提交期限。因此，本文给出可调整的六周安排；数据规模和完成日期是建议，不是已取得的结果或固定承诺。本文是后续实施方案，拟新增的数据管道、接口与表均按计划标明。

阅读顺序：先看第 1 至 3 节确定范围，再按第 6 节逐阶段实施；开发时使用第 4、5、7、8 节；实验与答辩使用第 9 至 12 节；附录 A 覆盖当前全部接口，附录 B 给出可直接交给 AI 的阶段指令。

## 1 当前项目全盘基线

### 1.1 已有工程与业务能力

当前工作区采用 Vue 3 与 TypeScript、Pinia、Axios、Element Plus、Vue Flow 和 ECharts；后端采用 FastAPI、Pydantic、SQLAlchemy、MySQL 和可替换的 AI Provider。后端基本遵循 Router → Service → Repository → Model 的依赖方向，前端统一通过 API 模块访问后端。

本次从实际 ORM 与生成的 OpenAPI 核对：34 张业务表、81 个外键约束、17 个接口模块、96 个去重路径、136 项 HTTP 操作。HTTP 操作分布为 GET 57、POST 52、PUT 10、PATCH 4、DELETE 13。这些数字描述代码范围，不代表测试通过数量或真实用户规模。

| 业务板块 | 当前能力 | 毕业设计中的用途 |
| --- | --- | --- |
| 账号与校园身份 | 注册登录、JWT、会话撤销、邀请、角色与账号管理 | 演示认证与数据访问边界 |
| 项目与个人学习 | 项目、课程、计划、任务、学习记录 | 提供首版学习行为数据源 |
| 校园教学 | 班级、任务、提交版本、教师反馈与通知 | 展示 V1 退回到 V2 通过的业务闭环 |
| 作品社区 | 发布快照、审核、浏览、评论、点赞、收藏与治理 | 提供可选浏览分析及成果展示 |
| AI 与工作流 | Context、结构化 Agent、DAG 执行、运行记录与失败续跑 | 作为应用辅助能力与扩展研究方向 |
| 统计与报告 | MySQL 聚合图表、个人周期 AI 学习报告 | 复用页面和图表基础，作为新旧计算口径对照 |
| 前端表现 | Campus Studio 页面、响应式布局、图表与交互优化 | 保持已有视觉方向，增加分析入口 |

### 1.2 已有成果与未实现内容

现有统计由 SQLAlchemy 查询 MySQL 业务表，不能描述成 Spark 计算结果。当前依赖与业务脚本中未发现 PySpark 离线 ETL、ODS／DWD／ADS 管道或 Spark 作业管理。

学习终态约束、计划与既有任务关系约束、AI 报告事实数字校正已有源码及 L1 至 L3 报告，应保留并回归。L4 历史记录证明过隔离 API 主线与清理通过，但完整浏览器主线仍有待补证；它不能直接代替新增分析流程的验收。

仓库已有 AI 引导式工作流方案 W0 至 W4、毕业整改路线 R0 至 R5，以及生产与试点规划 P22 至 P24。本文统一其优先级：Spark 分析与毕业交付是本阶段主线；AI 引导式工作流是主线完成后的应用扩展；平台级成本治理、生产部署及真实班级试点分别按后续条件启动。

## 2 毕业设计目标与交付范围

### 2.1 建议题目与研究问题

建议与导师沟通的题目为“基于 Spark 的校园学习行为分析与可视化系统设计与实现”。AI 可在摘要和功能章节作为辅助能力介绍；如果将其写入题目，就需要相应的独立实现和评价材料。

论文围绕三个问题展开：异构业务记录如何形成可复现的数据集；学习行为指标如何通过清洗、关联和聚合得到可信结果；批处理结果如何通过权限受控的接口和可视化支持学习复盘。用已有校园业务解释数据来源，用实际 Spark 程序和实验解释专业技术内容。

### 2.2 必做与选做

| 优先级 | 工作内容 | 完成依据 |
| --- | --- | --- |
| 必做 | 保持已有核心业务可用，修复影响数据准确性的已知问题 | 核心调用链与回归证据 |
| 必做 | 规范现有全部接口的说明、权限、错误、分页、时间与版本约定 | 全量目录、契约卡与 OpenAPI 对照 |
| 必做 | 业务快照抽取、PySpark 清洗、Spark SQL 聚合与批次重跑 | 作业、输入样本、预期结果与运行记录 |
| 必做 | 首版三个学习指标、结果入库、新查询接口与图表 | 同一批次的源数据到图表核对 |
| 必做 | 正确性、规模实验、论文、答辩演示与代码讲解 | 可复现材料及实际测量结果 |
| 选做 | 社区 PV／UV、教学首版提交提前量 | 额外数据源与口径单独验收 |
| 选做 | AI 自动生成与分步引导实践流程 | W0 至 W3 完整闭环及 W4 评价 |
| 条件启动 | 真实模型调试入口收紧、部署、真实班级试点 | 面向非受控账号或学校要求时启动 |
| 远期扩展 | Kafka／Flink、分布式集群与复杂调度 | 核心毕业交付后另行立项 |

首版毕业交付的终点是：固定数据集能抽取、清洗、计算、发布和展示；指标有准确口径；相关接口有文档；实验可复现；核心业务仍可演示。到达该终点后转入论文与答辩收尾，后续扩展按剩余时间选择。

## 3 总体架构与实施边界

### 3.1 目标数据流

```text
已有业务 Vue → FastAPI → MySQL 业务表
                         ↓ 白名单只读抽取
                  ODS 不可变批次快照
                         ↓ PySpark 清洗与关联
                  DWD 规范明细与异常记录
                         ↓ Spark SQL 指标聚合
                  ADS 汇总文件与质量报告
                         ↓ 受控导入并发布批次
                  MySQL 分析结果表
                         ↓ 新增只读分析接口
                  Vue／ECharts 分析页面
```

Spark 以独立离线作业运行；FastAPI 查询已发布汇总。页面刷新不触发 Spark，也不在普通 GET 请求内等待批处理。原有 /statistics 接口继续保留 MySQL 业务聚合含义，离线结果使用独立命名空间和批次信息。

ODS、DWD、ADS 是数据处理层次；第一版可以用本地文件和少量 MySQL 汇总表承载。部署采用单机开发与演示模式，优先完成 PySpark DataFrame 和 Spark SQL 的真实处理过程。单机 local 模式实验只能证明该环境下的处理能力，论文要据此解释结果。

### 3.2 环境与目录建议

建议新增独立的 data_pipeline 目录，包含 extract、transform、aggregate、load、tests 和 README；其命名在实施时与仓库结构核定。原始数据、Parquet、运行日志和实验输出使用独立数据目录，不将大文件、连接凭据或个人数据提交到 Git。

开发前核对 Python、JDK、可用内存和磁盘。Spark 与 Python／Java 的兼容性按固定版本的官方说明核对，例如 Spark 4.0.1 安装文档提供相关要求；本项目应在最小读写与聚合试运行通过后记录并固定实际版本。新增依赖放入独立数据处理环境，避免改变后端已有运行环境。Windows 环境先验证当前可用路径；确有运行障碍时，再评估 WSL2。

首次作业建议固定线程数，如 local[2]，并记录内存、分区与 shuffle 配置。需要更多并行度时依据实验结果调整，不以线程数量作为大数据规模证据。官方参考见第 13 节。

## 4 数据来源与分层设计

### 4.1 全部业务表分组

| 分组 | 数量 | 当前表 |
| --- | --- | --- |
| 身份与安全 | 5 | users、campus_memberships、campus_invitations、password_resets、account_audits |
| 个人资源 | 4 | projects、tags、project_tags、courses |
| 学习管理 | 4 | learning_plans、daily_tasks、learning_records、learning_reports |
| 工作流 | 4 | workflows、workflow_nodes、workflow_edges、workflow_runs |
| AI 调用 | 2 | ai_requests、ai_results |
| 社区与治理 | 8 | comments、likes、favorites、project_views、community_publications、community_publication_versions、community_governance_actions、community_governance_cases |
| 教学协作 | 7 | teaching_classes、class_memberships、teaching_assignments、submissions、submission_versions、feedback、notifications |

已有提交版本、社区发布快照和审计记录承担历史追溯职责，继续保留。分析侧通过汇总结果减少查询成本，业务侧继续承担事务与权限，不把原有业务表改造成数仓表。

### 4.2 首版抽取字段与实际含义

| 来源 | 首版所需字段 | 必须解释的口径 |
| --- | --- | --- |
| learning_records | id、user_id、关联 ID、record_type、duration_minutes、occurred_at、必要来源标记 | 分钟是用户记录值；无 updated_at，允许编辑删除 |
| daily_tasks | id、user_id、plan_id、project_id、status、scheduled_date、completed_at | 保存批次时任务状态；预计分钟不当作实际学习时长 |
| projects | id、owner_id、状态与必要技术字段 | 当前技术与状态快照；任务衍生进度需遵循已有算法 |
| project_views 选做 | id、project_id、user_id、viewed_at | 已成功记录的社区详情浏览事件 |
| submissions／submission_versions 选做 | 提交 ID、任务 ID、班级 ID、学生成员 ID、截止快照、版本号、提交时间 | 成功落库的提交版本，缺少失败请求及未提交尝试 |
| campus／class_memberships 选做 | ID、user_id、class_id、角色与状态 | 当前授权和关系映射，不还原未记录的历史角色 |

白名单不抽取邮箱、密码哈希、Token、邀请凭证、完整项目正文、代码正文或完整 AI 提示词。内部 ID 仅用于关联与权限。来源标记从 JSON 中提取所需字段，避免将整个自由 JSON 直接进入分析层。

### 4.3 ODS 快照

第一版按统计窗口做完整批次快照：在受控只读一致性事务内抽取必要字段，结束事务后交给 Spark 处理。不同 JDBC 连接不能自动视为共享同一源快照。数据量增长后再评估分页抽取或增量方案。

learning_records 可修改、删除且没有 updated_at，因此仅靠最大 ID 或 created_at 无法完整捕获变化。先采用全量窗口快照并重算，避免首版引入 CDC 和日志采集复杂度。

每批保存 batch_id、dataset_kind、抽取开始与结束时间、source_cutoff、统计周期、业务时区、源行数和规则版本。snapshot 中的数据与元信息一经形成便保持不变；相同快照用于重跑和结果核对。抽取暂存文件可用明确 schema 的 CSV，完成后由数据处理环境转换为 Parquet 并固定字段类型。

### 4.4 DWD 明细

首版包括学习记录明细和任务批次快照，选做时加入社区浏览和提交版本。分别明确“一条记录”“一个任务截至批次的状态”“一次已记录浏览”“一个提交版本”的粒度。

使用真实源主键去重；同主键同内容可去重，同主键冲突内容进入异常文件，不用任意保留一条掩盖问题。校验字段类型、有效枚举、时间、关联与分钟范围；NULL 时长单独统计，不填成真实零分钟。缺少关键归属、日期或非法状态的行保留异常原因。质量检查记录输入、去重、有效、异常的行数及相互关系。

业务 DATETIME 沿用 UTC 语义，再按 Asia/Shanghai 归属业务日；查询窗口用本地起始日零点到结束日次日零点的左闭右开区间并转换为 UTC。scheduled_date 已是 DATE，直接作为计划日期，不做 UTC 转换。

### 4.5 ADS 汇总与发布

核心版拟新增批次元数据与用户日学习汇总两类表。批次表记录来源、周期、规则版本、状态、耗时与质量数量；用户日汇总按 batch_id、user_id、biz_date 唯一，保存记录分钟、NULL 时长数、记录数及任务各状态计数。社区项目日汇总和教学任务汇总随选做指标另行增加。

只回写图表所需汇总，明细继续保留在 Parquet。DDL、索引与角色访问范围在 B2／B4 实施前形成可审查设计，新增表使用增量迁移，并核对现有业务回归。

先写未发布批次，核对行数和固定样本后，在短事务内标记 completed。查询只读取已完成批次；失败继续使用上一成功批次。前端选定 batch_id 后所有图表使用同一批次，避免不同图表读到不同次计算。

作业以显式 batch_id 重跑；同一快照与规则应产生相同指标。completed 批次的汇总禁止覆盖，同输入重试可复用既有结果；确需重算或源数据与规则变化时创建新批次。仅未发布目标批次允许清理和重写暂存与汇总，禁止按整表清空实现重跑。

## 5 指标定义与图表设计

### 5.1 核心三个指标

| 指标 | 计算定义 | 展示与样本处理 |
| --- | --- | --- |
| 已记录学习分钟 | 按 occurred_at 业务日汇总非 NULL 的 duration_minutes | 同时显示记录数量和缺失时长数量；名称使用记录分钟 |
| 有学习记录用户数与个人活跃天数 | 日内去重 user_id；个人周期内去重存在记录的业务日 | 教学自动生成记录单列来源；不是全站登录 DAU |
| 按计划日期任务完成率 | 截至批次 completed 任务数／该 scheduled_date 下全部保留任务数 | 沿用当前报告包含 cancelled 的分母，同时展示取消数；分母为零显示无样本 |

例如某日保留 4 个任务，其中 2 个完成、1 个进行中、1 个取消，当前口径完成率为 2／4。若将来选择排除取消任务，使用新口径版本并同步接口、图表与论文，不悄悄改分母。

教师通过成果可能自动生成 duration_minutes 为 NULL、来源为 teaching_submission 的学习记录。该记录证明教学活动被记录，不能据此虚构学习分钟。task.completed_at 则用于“标记完成时间”的分析，与 scheduled_date 口径分开。

### 5.2 选做指标

社区浏览 PV 为按业务日统计 project_views 行数，账号 UV 为对应去重 user_id；刷新或重试成功记录也可能增加 PV。只称为已记录社区浏览，不推断匿名访客、停留时长或全站流量。

教学选做指标采用首版提交提前量：以 version_number 为 1 且截止快照有效的提交为样本，计算 assignment_due_at 减 submitted_at 的分钟差，展示分布、中位数、样本数及缺失数。当前 API 在达到截止时间时拒绝提交，所以正常业务数据的首版按时率理论上为 100% 或无样本，不适合据此评价学生按时表现。全班提交覆盖率需要另行定义应提交人员，提交 API 成功率需要失败请求事件；合成迟交样本只用于异常规则实验。

技术栈趋势、AI 请求时延、工作流完成率可继续扩展，但每项都先补口径。当前技术栈百分比存在前 N 项分母含义，应在文档说明；若只展示数量可以保持现状。新增分析采用全量明确分母，多标签覆盖率之和可能超过 100%，不能套成互斥类别占比。

### 5.3 页面与数据权限

复用现有 ECharts 和视觉样式，新页面显示数据集类型、统计周期、生成时间、数据截止时间和批次。核心图表包括记录分钟趋势、记录活跃情况、任务状态分布与完成率；支持日期筛选、刷新已发布结果、空样本与失败提示。

| 角色或数据集 | 首版可读范围 |
| --- | --- |
| 学生或普通个人账号 | 本人的学习日汇总 |
| 同班教师 | 当前授权班级的教学任务汇总，选做时提供 |
| 管理员 | 明确授权的总体汇总与批次状态 |
| 合成规模实验 | 独立实验输出；若提供展示，仅给受控实验汇总 |

daily_tasks 与 learning_records 没有 class_id，不能凭班级成员身份把学生所有个人学习数据给教师。现有 statistics 是平台聚合，新分析接口要按新用途独立校验权限。

## 6 分阶段实施步骤

### B0 固定范围与指标

预计半天至一天。确认建议题目、首版三个指标、选做内容和答辩主流程。用一张需求-实现-验证矩阵把每个目标连接到页面、API、数据源、作业与验收证据；更新已有 R0 范围和主张，不重新铺开全部业务开发。

交付物：范围页、指标卡、数据权限矩阵和任务清单。验收：每项必做工作有明确输入、产出和完成条件，计划能力与已有能力区分清楚。

### B1 规范已有代码与接口

预计两至四天。先冻结当前 OpenAPI 与调用方基线，逐模块填补接口契约卡。优先检查学习进度一致性、现有统计分母和错误文档；保留 L1 至 L3 的规则。Learning 与 Workspace 重复的进度计算仅在明确调用关系后收敛，避免重新搭建通用框架。

学习并发修复需要串行化同一计划写入，并在短业务事务内用当前状态完成校验、任务更新与重算；不能仅在请求早期普通查询之后添加父计划锁，再沿用旧快照聚合。跨计划移动按稳定 ID 顺序处理，保持既有终态与所有权规则。

统一实际错误模型与 OpenAPI，保留 error.code、message、request_id；字段校验提供脱敏位置和原因。既有 PUT 部分更新在文档写明，不批量改路径或方法。AI 慢调用连接占用问题作为收尾项；若演示出现资源问题，再安排短事务改进。

交付物：全量接口目录、权限与错误说明、必要修复和相关回归。验收：旧接口仍可调用；核心数据一致；变更接口的文档、类型与返回一致。

### B2 抽取快照与搭建数据处理环境

预计两至三天。先核对并固定 Python／JDK／Spark 环境，再实现最小白名单抽取、批次元信息与固定小样本。确定 ODS 与 DWD schema、字段类型、时区和异常规则；学习记录采用窗口快照策略。

只读抽取真实开发数据时使用现有授权范围；端到端写入验收另用明确确认的专用空库。准备分析结果表设计与增量迁移方案，说明兼容影响后再实施。合成性能数据直接生成独立文件，避免向业务库灌入大批虚构记录。

交付物：独立环境说明、抽取入口、样本、数据字典、批次元信息与拟议 DDL。验收：源字段白名单清楚；样本能稳定复现；零记录、跨午夜、NULL 和日期字段得到正确处理。

### B3 PySpark 清洗与 Spark SQL 聚合

预计三至五天。实现显式 schema、去重、异常分流、业务日归属与必要关联；用 DataFrame 完成清洗，再用 Spark SQL 计算三个核心指标。保存 DWD、ADS、质量计数及实际运行参数。

对固定正确答案逐项比较，再重跑同一快照，确认结果一致。出现错误时保存失败原因和中间数据，修复对应规则。作业入口需有参数、退出状态和可读日志，不能只保留一次性 Notebook 截图。

交付物：可运行作业、规则说明、预期结果、实际结果与正确性检查。验收：核心指标全部与已知答案一致；异常行可追溯；同批次重跑稳定。

### B4 结果发布与前后端闭环

预计三至五天。实现汇总导入、批次 completed 发布与失败保留上一批次；新增只读分析接口及类型化前端调用。图表从新接口读取批次结果，现有统计页入口继续保留。

新接口先确定本人、班级和总体汇总范围，后端负责最终授权。处理未发布、无数据、过期数据、无样本、日期切换和请求失败。日汇总里的比例保留分子分母，前端不重复发明统计算法。

交付物：迁移、导入入口、接口契约、分析页面与演示样本。验收：能从固定源样本追踪到 ODS、DWD、ADS、MySQL、API 和图表；刷新后保持结果；失败不会展示半批次。

### B5 正确性与规模实验

预计三至五天。固定小样本做边界验证；用固定种子生成两至三档合成数据，记录实际行数和分布。每档运行相同清洗与聚合，预热后至少重复三次；分别记录抽取、清洗、聚合、写回和端到端时间。

与同口径的 Python 标准库实现或受控 MySQL SQL 结果比较；先验证答案一致，再比较耗时。小规模数据下，Spark 启动成本可能占较大比例，两种实现的性能优劣以实测结果解释。保留 Spark explain、任务阶段和 shuffle 等能支持瓶颈分析的证据，不预设 Spark 必然更快。

交付物：环境与参数表、数据生成说明、原始测量、统计结果和实验分析。验收：方法可复现，结果不挑选；合成与真实记录分开说明；规模结论与实际运行环境对应。

### B6 论文与答辩收尾

预计三至五天，并从 B0 起同步积累材料。统一 README、数据字典、API 文档、图表标签和论文口径；复用 R1 至 R5 的证据整理方法。补齐真实 UI 主线，不把接口通过替代页面演示。

冻结一套演示输入与已发布批次，录制数据处理和系统展示。整理模块说明、关键代码位置、实验结果、失败案例、导师问题与回答。提交前核对每个“已实现”和每个数字的证据。

交付物：论文、答辩 PPT、演示脚本、视频或截图、关键代码导读和提交清单。验收：本人能解释每个指标分母、Spark 作业的输入输出、数据发布机制和权限边界。

## 7 代码规范与冗余整理方法

### 7.1 前后端与数据处理职责

前端页面负责组合与交互；API 模块负责 HTTP 和 DTO；Pinia 只保存确有共享需要的状态。沿用现有视觉与 ECharts 组件，处理加载、空数据、失败和过期响应。服务端保持 Router 接入、Service 规则与授权、Repository 查询与持久化，外部响应继续使用明确 Schema。

数据管道按抽取、清洗、聚合和发布组织，指标规则集中在有业务含义的位置。每个函数说明输入粒度、时间口径与输出，不创建堆放无关功能的 common／helpers。使用项目已有依赖，新增 PySpark 环境与必要库独立记录。

### 7.2 每次修改的检查顺序

先读当前实现、调用方与测试，写明一个阶段的范围；实现最小完整变更；检查差异与调试代码；运行相关检查；最后更新阶段结果。新增依赖、公共 API、数据结构或跨模块改造先给出影响与设计，再进入实施。

前端沿用 pnpm typecheck、pnpm build；后端沿用现有 unittest 与 pip check。涉及新 Spark 规则时运行小样本正确性和重跑测试，涉及接口则做契约与权限检查。当前前端未定义独立 Lint／格式化命令，后续按已有工具报告，不把“未运行”写成“通过”。

### 7.3 冗余清理准则

仅在有调用证据时清理无用函数、组件、样式和调试内容；重复规则先比较语义、权限和生命周期，再决定复用。Learning 和 Workspace 的进度计算是可核对候选；个人与教学的权限规则不因字段相似就合并。版本、快照、审计与业务证据继续保留。

代码说明使用中文解释原因与约束，标识符使用清楚的英文。每个阶段记录文件变化、验证结果和恢复方式；避免在文档、日志、截图或 Git 中留下密钥和个人信息。

## 8 全部接口规范与新增分析契约

### 8.1 现有接口收口方法

附录 A 是当前 136 项操作的全量清单。按 17 个模块逐项建立契约卡，覆盖公开握手、个人资源、校园教学、社区治理和 AI 入口；最终覆盖率按“已完成契约卡的操作数／基线 136 项操作”统计，新增接口单列。

每张契约卡记录：用途与调用页面；方法和路径；请求字段、类型、必填、长度、范围与 NULL 含义；响应模型与样例；实际状态码与错误代码；角色、资源归属和班级范围；分页、排序、时间、版本与幂等规则；涉及的 Service／Repository／表；至少一个正常和一个关键异常用例。

OpenAPI 与 /docs 作为可读入口，中文目录帮助导师理解业务。生成客户端或接口类型前，先校正错误 Schema；不把服务端授权简化成 Swagger 的 Bearer 标记。明确已有 expected_version、expected_revision、expected_auth_version 和 request_key 各自适用的操作，避免给所有 CRUD 增加不必要机制。

### 8.2 拟新增只读接口

以下命名是 B4 的契约草案，当前不存在；最终实施前与前端调用方确认。

| 拟议方法与路径 | 用途与权限 | 关键返回 |
| --- | --- | --- |
| GET /api/v1/analytics/offline/batches | 列出本人或明确授权范围的可用批次 | batch_id、周期、来源、截止时间、完成时间、规则版本 |
| GET /api/v1/analytics/offline/me/daily | 查询本人日汇总；user_id 由认证决定 | 日期、分钟、缺失数、记录数、任务分子分母与状态计数 |
| GET /api/v1/analytics/offline/admin/overview | 管理员总体汇总与质量数量 | 活跃记录用户数、分钟与任务汇总 |
| GET /api/v1/analytics/offline/classes/{class_id}/assignments | 选做；同班教师教学任务分析 | 首版提交提前量、样本与缺失数量、任务与班级范围 |

查询参数包括明确 batch_id、统计起止日和有界分页；批次与日期不匹配返回可操作错误。核心响应同时带 dataset_kind、timezone、source_cutoff 和 metric_version，避免只返回脱离来源的数字。未完成或无可用批次按约定返回等待提示；空结果返回空数组；比例分母为零返回 NULL。

离线作业先用受控 CLI 运行，新增 HTTP 启动作业入口留待出现实际交互需要后设计。所有查询通过后端 Repository 访问汇总，浏览器不直接连接数据库，也不允许用查询参数选择任意用户的数据。

## 9 验证与实验方案

### 9.1 必须覆盖的正确性场景

| 场景 | 核对内容 |
| --- | --- |
| 普通记录与多个任务 | 分钟、活跃日、任务状态和比例与人工答案一致 |
| 午夜与时区边界 | UTC 转业务日正确，DATE 字段保持原语义 |
| NULL 与零 | 缺失分钟、真实零、无记录和无样本分开处理 |
| 重复与冲突输入 | 去重稳定；冲突内容进入异常记录 |
| 修改与删除源记录 | 新窗口快照重算反映变化，旧批次可追溯 |
| 同计划并发写入 | 完成数量与计划进度一致，终态规则保持成立 |
| 批次失败与重跑 | 不发布半成品；上一批次可读；同快照重跑一致 |
| 个人与跨班访问 | 本人可读、越权拒绝、教师不读私人学习明细 |
| 可选浏览和提交 | PV／UV、首版截止、版本与审核分母符合定义 |

### 9.2 数据规模与测量方法

候选规模为一万、十万和一百万条合成记录；先试跑小档，再按本机内存和磁盘选两至三档，向导师报告实际完成规模。规模实验优先使用独立文件，避免把百万条样本直接写进业务库。

固定种子、用户数量、日期跨度、NULL／异常／重复比例与分区参数。每次测量记录软件版本、CPU、内存、数据量、冷／热启动、缓存条件、Spark 线程、分区、耗时、异常和输出行数；重复测量保存原始值，报告中位数与范围。Python 或 MySQL 对照必须采用相同筛选、NULL 和分母规则。

实验图包括规模与端到端耗时、各阶段耗时、质量计数和准确性对照。结论只覆盖实际测量的单机与数据分布；集群扩展和真实使用效果留作展望。

### 9.3 答辩可复现条件

保留固定小数据集和预期结果，提供一次运行的参数与输出位置。数据库写入验收使用明确确认的专用空库，验证后只清理本次虚构资源，保存清理结果。现有 verify_integration.py 等脚本可能写库，不能当作只读检查直接在业务库运行。

真实 AI 模型评价另存模型、提示、用量和人工评分。Fake Provider 证明流程及结构，不作为模型正确率、教学效果或费用数据。答辩当天优先使用已完成批次与固定案例，Spark 重跑可以提前录制并现场展示关键步骤。

## 10 AI 引导式工作流与远期路线

### 10.1 AI 引导方案的保留与优先级

已有方案提出自然语言生成实践流程、显式前序产出引用、等待学生提交、针对性评审、修正与复盘。它与 Spark 分析是两项能力：引导学习数据处理任务，不能替代真正执行 Spark、核对指标与完成规模实验。

建议在 B0 至 B4 核心闭环稳定后决定是否投入 W 路线；若时间紧，使用已有 AI 工作流作为辅助展示即可。若选择实施，首个案例沿用“Python 学习记录 CSV 清洗与每日学习分钟统计”，后续再增加 PySpark 版本。

| 原阶段 | 做法 | 完成条件 |
| --- | --- | --- |
| W0 场景与契约 | 固定 6 步输入、产出、验收和状态 | 每步任务与提交物明确 |
| W1 草案生成 | 自然语言、必要追问、受限节点、服务端图校验与预览 | 合法草案可确认；不支持能力不伪装成可执行 |
| W2 分步引导 | 引导会话、单步调用、产出绑定、等待提交与版本恢复 | 提示到提交到评审能推进，刷新后恢复 |
| W3 成果落实 | 用户确认形成学习任务／记录，保留实践尝试和复盘 | 建议、学生自测和人工核对来源清楚 |
| W4 质量评价 | 固定正确与错误案例、真实模型评分和差例 | 流程证据、AI 质量、使用效果分别报告 |

保留当前 DAG 与旧运行接口，推荐新增引导会话模式；人工等待状态不直接塞进旧执行语义。所需新接口、结果结构和持久化设计在实施前单独审查。AI 评审属于内容评审，代码是否真正运行与通过测试需要独立证据。

### 10.2 P22 至 P24 与实时处理

P22 平台额度与质量治理、P23 生产部署与隐私、P24 真实课堂试点维持后续规划。毕业阶段只落实当前使用需要的边界：真实 Key 面向非受控账号前限制 AI 调试入口；实际部署时核对配置与备份；真实试点时取得参与和数据使用条件。

Kafka／Flink 用于后续实时事件分析；需要先设计真实事件粒度、采集与重放、延迟和一致性，再另做实时实验。只有任务书或真实场景需要集群时，再扩展 Hadoop／HDFS、调度平台或集群部署。

## 11 论文结构与导师答辩准备

### 11.1 建议论文结构

| 章节 | 主要内容与材料 |
| --- | --- |
| 绪论与相关技术 | 场景、研究问题、范围，Spark／SQL／可视化相关文献 |
| 需求分析 | 核心数据链路、角色权限、需求-实现-验证矩阵 |
| 总体设计 | 业务系统与离线管道架构、数据分层、接口与批次设计 |
| 数据处理实现 | schema、抽取、清洗、关联、聚合、异常与重跑 |
| 系统实现 | 汇总发布、API、前端图表与已有业务复用 |
| 测试与实验 | 正确性、规模与性能、权限、失败恢复及结果分析 |
| 总结与展望 | 已完成范围、局限、AI 引导与实时处理扩展 |

图表至少包含总体架构、数据流、核心业务 ER、分析表关系、批次发布时序、权限矩阵、指标口径表和实验结果。文献从可核验来源获取，官方文档支撑实现说明，历史开发报告用于工程证据。

### 11.2 十分钟演示顺序

第一分钟介绍场景与题目；第二分钟展示已有记录和任务来源；第三至第五分钟展示批次、清洗异常、Spark 聚合及已知答案；第六至第七分钟展示新接口和同批次图表；第八分钟解释规模实验；第九分钟展示权限或失败恢复；第十分钟说明已完成边界与下一步。

准备五条已有代码调用链：登录与 CurrentUser；任务完成到计划进度；工作流执行到 AI 记录；教学 V1 退回至 V2 通过；MySQL 统计与个人 AI 报告。新增重点讲解一条计划完成后的 Spark 全链路。完成任务接口不自动生成学习记录，个人报告与平台统计的范围也不同，讲解时保持准确。

### 11.3 常见问题与回答依据

| 导师问题 | 回答要点与应准备证据 |
| --- | --- |
| 为什么现有 MySQL 之外还使用 Spark | 展示多源清洗、批量关联和分层处理；用实验说明适用范围 |
| 数据从哪里来，是否真实 | 区分固定演示业务、授权记录和合成规模数据，给生成与抽取说明 |
| 数据量不大还能叫大数据方向吗 | 展示实际 Spark 程序、处理流程和规模实验，并说明单机局限；由导师确认题目与专业要求 |
| 分钟和活跃用户怎么定义 | 出示指标卡、NULL 处理、来源与分母，现场核对小样本 |
| Spark 是否一定更快 | 出示同口径测量和启动成本，按结果回答 |
| 重跑或中途失败怎么办 | 出示不可变快照、batch_id、未发布批次和上一成功结果 |
| 教师能否看到学生所有数据 | 展示角色矩阵和跨用户／跨班拒绝用例 |
| 原系统有没有被改坏 | 展示旧接口基线、关键业务回归和迁移范围 |
| AI 有什么作用，能否保证代码正确 | 区分辅助建议、结构校验、真实运行与人工核对 |
| 本人理解和完成了什么 | 按实际记录说明需求、设计选择、实现、验收与 AI 辅助，能解释关键代码 |

## 12 六周节奏与交付清单

| 时间建议 | 阶段重点 | 当周应交付 |
| --- | --- | --- |
| 第 1 周 | B0 与 B1 | 范围、指标、全接口目录、必要数据修复与规范 |
| 第 2 周 | B2 | 环境、白名单抽取、ODS、数据字典与小样本 |
| 第 3 周 | B3 | DWD、Spark SQL、ADS 与正确性结果 |
| 第 4 周 | B4 | 发布、查询接口、图表和完整数据链路 |
| 第 5 周 | B5 | 规模实验、原始数据、性能与质量分析 |
| 第 6 周 | B6 | 论文、PPT、演示、代码导读和最终核对 |

论文材料从第一周同步积累。若只有四周，先保留三个核心指标与本人分析页面，合并阶段，减少选做；若有额外时间，再做社区／教学指标或 W0 至 W4。每周根据已完成证据调整，不以预估工期宣称完成。

最终清单：范围与需求矩阵；全部接口目录和契约卡；数据字典与核心 ER；可运行抽取／Spark／发布入口；固定样本与预期结果；批次与质量记录；MySQL 汇总与新 API；分析页面；旧业务回归与权限证据；规模实验原始值与图表；论文与 PPT；演示脚本与关键代码说明。

与旧路线对应：R0 由 B0 承接；R1 在 B1 至 B6 积累；R2 在 B4 与 B6 补齐；R3A 由 B5 承接；R3B 随 AI 选做评价；R4 和 R5 在 B6 收尾。L1 至 L3 保留回归，L4 补页面证据，L5／L6 按统计口径与真实模型使用条件安排。旧计划中的未完成项只有满足本次范围时进入必做。

## 13 依据与后续维护

本版优先依据用户当前确认的毕业设计目标、引用会话“大数据毕业设计方向”中的 Spark 离线路线，以及当前工作区源码。早期计划与本版优先级不同的内容，作为历史资料保留；后续更新以实际阶段成果、导师意见和验证结果为准。

项目依据：README.md；backend/app/models；backend/app/api/v1；backend/app/repositories/statistics.py；backend/app/repositories/learning_report.py；frontend/package.json；开发相关文档/开发规划/20260927-毕业设计整改方案.md；开发相关文档/开发规划/20261014-AI引导式工作流改进方案与验收目标.md；开发相关文档/阶段报告/20260928-L4-隔离环境主线验收报告.md；现有 R 与 L 阶段提示词。

实施参考：[Spark 4.0.1 PySpark 安装说明](https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html)、[Spark 作业提交](https://spark.apache.org/docs/4.0.1/submitting-applications.html)、[Spark Parquet 数据源](https://spark.apache.org/docs/4.0.1/sql-data-sources-parquet.html)。实施时以最终固定版本的对应文档核对，本文未据此宣称本机 Spark 环境已经安装或验证。

本文维护方式：每完成一个 B／W 阶段，在同一清单记录已完成、验证证据和剩余项；涉及接口或口径变化同步更新文档。下一步从 B0 与 B1 开始，以数据准确性和接口说明收口为入口，然后进入独立 Spark 环境与样本开发。

## 附录 A 当前全部接口清单

以下目录由当前工作区生成的 OpenAPI 提取，统一前缀为 /api/v1，按模块列出全部 136 项操作。目录标明方法、路径与用途；详细字段以对应 Schema 与 /docs 为准，业务授权以 Service 为准。这里只列已有接口，第 8 节拟新增接口不计入此基线。

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


## 附录 B 可直接使用的阶段开发指令

### B0 与 B1 指令

请依据本计划第 1、2、7、8 节，读取当前 ScholarHub 代码和已有变更，先输出范围、指标卡及全部 136 项接口的规范收口清单。优先检查学习数据一致性和错误响应文档，保留已有路径、DTO、权限与 L1 至 L3 规则。先给最小设计和验证方式，再实现本次明确授权的一个问题。涉及公共接口、依赖或数据结构变更时，先说明兼容影响并等待确认。完成后给中文阶段结果和证据。

### B2 指令

请只实施已确认的 B2 范围。核对 Python／JDK／Spark 环境，提出独立环境与固定版本方案，再按批准方案搭建。基于 learning_records 和 daily_tasks 白名单设计快照与显式 schema，保留 NULL、UTC 与 DATE 含义，不使用 ID 增量代替完整修改删除捕获。先完成小样本与数据字典；写库验收必须使用明确确认的专用空库。交付抽取入口、批次元信息与验证结果。

### B3 指令

请只实施本计划第 4、5、6 节的核心三个指标，基于已固定 ODS 样本编写 PySpark 清洗和 Spark SQL 聚合。先核对人工正确答案，覆盖重复、冲突、NULL、取消、无样本与时区。保存异常原因和质量计数，验证同快照重跑一致。不要修改已有业务接口或引入实时计算平台；完成后提供作业、参数、实际结果和相关测试。

### B4 指令

请先给出分析结果表、增量迁移、批次发布和新只读 API 的可审查设计，取得接口与数据库变更确认后实施。保持原 /statistics 和已有功能。只读本人日汇总，管理员总体与教师班级范围按明确授权实现；图表固定使用同一 completed 批次。验证失败保留旧结果、空样本、越权与原业务回归，最后交付接口契约和页面证据。

### B5 指令

请先固定实验环境、数据规模、种子、异常分布、重复次数与测量口径，再生成独立合成文件。先比较正确答案，再运行相同规则的规模实验，至少保存三次测量及阶段耗时。区分启动与处理成本，不预设 Spark 更快，不把合成记录说成真实用户行为。完成后提供原始结果、分析图和可复现步骤。

### B6 指令

请基于实际已完成阶段整理论文、答辩材料与关键代码导读，复核已实现主张、指标口径、接口数和实验数字。按十分钟主线组织演示，补足真实页面证据，提供导师问题与有依据的回答。保留未完成项在后续计划，区分 AI 建议、真实运行和人工核对；不要虚构使用效果或论文实验结果。
