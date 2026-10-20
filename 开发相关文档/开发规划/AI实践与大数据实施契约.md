# AI 实践与大数据实施契约

版本：**V2-S01-r2**（继承r1已批准范围，仅修订评分方式）；日期：2026-10-20，Asia/Shanghai。本文固定本版设计、样例和评价方法。**A、B组r1列明设计已获用户批准；用户随后要求“用ai来评分把”，据此形成r2评分修订**。后续按用户逐阶段指令实施；设计批准不等于已执行迁移、接口上线，也不替代具体隔离库写入、真实模型输入与费用授权。确认状态以[确认记录](../阶段报告/AI大数据改造/V2/S01-确认记录.md)为准。

## 1 范围与停止线

| 项目 | 本版决定 |
| --- | --- |
| 首要用户 | 管理本人项目、个人任务且参加教学提交的学生；教师反馈为独立证据来源 |
| 具体困难 | 分散记录无法区分修订过程、当前教师确认和未知学习时长；界面总数缺少群组、分母与来源解释 |
| 主分析问题 | 同一提交群组截至同一快照，多少进入修订、多少获教师确认，首次反馈等待如何分布；这些与任务完成和记录覆盖如何并列解释 |
| 大数据必做 A | S00–S06：已有业务 → 一致性快照 → ODS/DWD/ADS → 受控发布 → 本人 API／图表；至少一个完整专题、固定答案与同口径规模实验 |
| 最小 AI 必做 B | S07–S10：固定 Python 学习记录 CSV 模板、独立会话、提交／静态反馈／恢复、早期质量评价、新事件分析及一次建议应用 |
| 选做 C | S11 自然语言草案和项目启动第二模板；默认未选择，跳过不阻塞 S12／S13 |
| 可演示成果 | 一批真实运行的 Spark 结果与独立答案一致；可回溯图表；一条首次正确可结束或修改后可恢复的实践；模型质量与成本原始结果 |
| 停止线 | 不做通用节点平台、在线学生代码执行、实时流系统、生产集群、全站重构、预测学习能力或无依据的学习效果提升 |
| 学校任务书 | 本次材料未提供可确认的正式任务书；未发现命名为任务书的现有材料。算法、集群、数据量、题目和格式硬指标均待核实，不作为校方要求杜撰 |

S00 当前基线为 main/9320d68；配置库学习记录、个人任务、教学班、提交和反馈为 0。这里的固定数据是**虚构设计样例**。S02 须在用户明确授权的隔离目标，经现有业务形成最小可信样例；不向业务库直接灌模拟数据。已有新 AI 会话不是 A 的依赖。

依赖固定为 S00→S01→S02→S03→S04→S05→S06→S07→S08→S09→S10→S12→S13；S11 只在明确选择后插入 S10 与 S12 之间。分段批准不授权自动执行后续阶段。

## 2 分析单位与固定时间语义

### 2.1 群组

- 第一版发布批次仅属于一个 `owner_user_id`，由认证／受控导出参数确定。学生归属沿 submissions.student_membership_id → class_memberships.campus_membership_id → campus_memberships.user_id 验证。
- 教学单位是一个 `submission_id`，即学生对一个教学任务的提交头。群组成员要求其 **V1 submitted_at 的业务日落在 period_start 至 period_end（含两端）**。后续版本不新增群组成员；分母是有过首次提交的群组，不是所有被布置任务的学生，不能称“全班提交率”。
- 所有计数读取同一一致性快照。修订指至少存在有效 V2；修订次数为有效版本数减一。确认指最新有效版本有匹配 ACCEPT Feedback、正确班级与教师关系且版本状态 accepted。
- 历史教师角色和同班关系用于来源核验；不因成员后来退出而否认已经保存的反馈。当前校园状态用于访问授权，不用于改写历史结论。
- 教师确认与教学学习记录是不同事实：ACCEPT 记录后来被删除、Feedback.learning_record_id 变 NULL 时，教师确认仍存在；只增加教学记录关联缺失质量数。教学来源的学习记录必须实际关联 ACCEPT Feedback、对应版本和同一学生，不能相信 JSON.source。
- 教师模板项目不等于学生项目。必要的学生项目来源只能取匹配版本的 source_project_id 并核对 owner；个人 daily_tasks 与 teaching_assignments 没有直接外键，不按标题强接，也不把教学通过自动视为个人任务完成。

### 2.2 窗口和截止

业务时区固定 `Asia/Shanghai`。UTC 时刻以带 Z 的 ISO8601 保存／传输，学习记录按 occurred_at 转换业务日；个人任务按原 scheduled_date（DATE）归组，不再偏移。时间事件右开：`event_time < source_cutoff`；日期窗口两端包含。版本和反馈取快照内已存在的有效关系。

source_cutoff 是**当前一致性快照的观测时刻**：在 REPEATABLE READ 只读一致性事务开启后首读数据库 UTC 时钟，另记 snapshot_started_at／snapshot_finished_at。它不是数据库时间旅行能力；当前状态不能被任意旧 cutoff 还原。状态按这一份快照读取，不用过滤 updated_at 伪造过去状态。固定文件中的截止时刻是样例定义，不声称现在能从业务库重取该历史状态。

记录抽取需要窗口内记录及其引用闭包；教学群组需要 V1 在窗口内的提交、截至快照的全部版本与反馈。窗口内教学记录的来源 Feedback 可能属于窗口外首次提交，仍需抽取必要父记录作来源验证，但不计入专题群组。禁止从窗口内截断的版本集合推断“没有修订”。

## 3 指标 图表与结论边界

比例统一保存分子／分母，百分比用 Decimal HALF_UP 保留 6 位；界面显示 1 位，不按显示值判完成资格。分母 0 时 percent=null，显示“无样本”。计数和已知分钟和为整数；空集合分钟和为 0，但同时返回 known_duration_count=0，不能解释成已知学习 0 分钟。

| 指标 | 定义 | 图表与可核对结果 | 可以／不能说明 |
| --- | --- | --- | --- |
| 背景记录 | 有效去重记录数、已知分钟、已知／缺失／已知零时长数、业务日去重数；来源分普通／可信教学／未核实声明 | 分钟趋势＋记录／缺失数，来源条图；D00 为5条、75分钟、已知3、缺失2、零1、活跃3日 | 记录覆盖；不能把缺失当0或把日志量当投入、掌握 |
| 任务过程 | 按 scheduled_date 的总数与 completed 数；cancelled 计总分母并单列 | 当前快照状态堆叠图；D00 为2/4=50%；D11 为199/200=99.5% | 当前任务兑现；不能据状态快照重建每日收盘完成率 |
| 逾期未完 | scheduled_date < local_date(source_cutoff)，且状态为 pending/in_progress；completed/cancelled 不计 | 任务分布与逾期计数；D00 为1 | 超过计划日仍未完；不是教学迟交、也不推断拖延人格 |
| 修订进展 | revised_count/cohort_count；revision_attempts=Σ(版本数−1) | 按 V1 业务日归组的修订／当前确认分组条图；D00 为1/3，33.3% | 群组内修订现象；不能断言修订越多越好 |
| 教师确认 | confirmed_count/cohort_count；另列首次确认、修订后确认、最新待评 | D00 为2/3，66.7%；首次通过1、修订后通过1、待评1 | 截至快照的教师认可；不是代码执行结果或普遍能力 |
| 修订后确认 | revised_confirmed_count/revised_count | D00 为1/1，100%，始终显示分子和小样本 | 描述该子群组；不能宣称修订导致学习提升 |
| 首次反馈等待 | 每个群组最早反馈.created_at − 对应版本.submitted_at；无反馈不补0，负时差为质量错误 | 固定区间[0,60)、[60,240)、[240,1440)、[1440,+∞)分钟；D00为1/1/0/0，覆盖2/3，均值45分钟 | 有反馈样本的等待；不是学习投入时长，未评不能当即时反馈 |

专题图按“首提交日归组，截至同一快照”标注。教师确认数可能大于修订数，**不绘制强制经过修订的漏斗**。S06 至少解释一个模式、一个反例、样本覆盖及不适用情形，并与独立参考答案核对。普通图表 GET 只读，不启动 Spark 或模型。

## 4 源 Schema 与质量规则

机器可读数据字典、主外键、nullable、当前 SQL 类型及显式 Spark 类型固定在[分析样例文件](../阶段报告/AI大数据改造/V2/S01-分析固定样例与独立答案.json)的 schema 中，版本 `scholarhub-source-1.0`。主源为 projects、daily_tasks、learning_records、teaching_classes、teaching_assignments、class_memberships、campus_memberships、submissions、submission_versions、feedback 共10表；源表不增加字段。

| 类型／来源 | 固定规则 |
| --- | --- |
| ID／计数 | JSON 整数→Spark LongType；正ID限制1至2^63−1，越界报质量错误，不能截断 unsigned BIGINT；次数／时长非负；版本与revision≥1 |
| 时刻 | UTC TimestampType；缺时区、非法日期拒绝；保存微秒，不默认为本机时区 |
| DATE | DateType，YYYY-MM-DD；不做二次时区换算 |
| 状态／角色 | StringType，值限定当前模型枚举；未知状态隔离并阻止发布，不用默认值掩盖 |
| nullable | 仅按源字段 nullable 和已列业务特例允许；NULL 与0分别保留 |
| 来源投影 | 只投影旧 JSON 的 source、submission_id、version_number 为 source_claim_projection，用于未核实声明计数；不抽取原始 JSON 正文，不证明教学来源 |
| 最小依赖 | 主体事实限定本人；班级、教师和成员依赖只带必要键、角色、状态供核验，不发布其他人的行级信息 |

白名单以 JSON 字典的逐字段列表为准。排除 title/description/content、提交 summary、request_payload、repository_url/ref、教师 comment、Project Context 私人正文、原始 Prompt、AIResult 正文、凭证和账户明细。AIRequest／WorkflowRun 仅作已有辅助运行指标，第一版10表分析不依赖它们；后续如需抽取其元数据另列变更。

users、learning_plans、courses 等未导出的辅助父表，在同一只读事务内做必要存在／归属预检，只保留质量计数；owner同时由认证／受控命令授权核对。plan_id／course_id在第一版是可空引用，不参与专题join。不能把未导出的辅助表误判为悬空，也不能跳过归属预检。10表间的引用在DWD再次核验；历史来源声明格式非法时保留为未核实声明，不让它升级可信来源。

学习记录没有 updated_at 且可修改删除，采用**完整窗口一致性快照**；所有表在同一只读一致性事务内分批读取，冻结期间不做模型、Spark或人工等待。依赖闭包需完整；快照完成后提交／关闭只读事务，离线计算不继续占用数据库事务。

质量规则 `quality-1.0`：

1. 同主键、同归一化内容的完全重复可去重并计数；同主键内容冲突隔离，整批失败，不能任取一行。提交版本按 submission_id+version_number 去重。
2. 主键／必需时间缺失、类型错误、越界、负时长、悬空关系、错误学生归属、班级不一致、版本序列断裂或状态／反馈矛盾均为阻止发布项，保留失败数量与错误码。
3. 真实 SET NULL 删除与 nullable 缺失保留质量数；Feedback 缺少学习记录不抹去已有教师确认。记录原样无可信 Feedback 时不能归类可信教学。
4. occurred_at≥cutoff 的学习记录不进入当前观测，另列 outside_observation_time；不补造历史事件。源修改删除需要新 batch_id，旧完成批次与旧报告不覆盖。
5. ODS 保留当前白名单快照；DWD 保存去重、归一化与来源判定，ADS 先按本人／业务日／提交群组聚合，再关联，禁止直接一对多 join 放大任务分母或分钟。

## 5 文件 批次 发布与接口契约 A

### 5.1 最小链路与元信息

Windows 只读导出 JSONL＋manifest → 不可覆盖 ODS → WSL/PySpark 显式 Schema → DWD Parquet → ADS 日汇总与专题 JSON／Parquet → Windows 受控导入 CLI → MySQL 完成批次 → FastAPI 本人只读 API → Vue/ECharts。

manifest 至少包含 batch_id（UUID，S03生成）、owner_user_id、period_start/end、business_timezone、source_cutoff、snapshot_started_at/finished_at、schema_version、metric_version=`learning-process-1.0`、rule_version、dataset_kind、各表行数和输入字节。输出包含质量数、分子分母、结果路径引用、实际运行版本／参数／耗时。artifact_ref 为受控相对引用，不接受客户端服务器路径。

dataset_kind 只取 `business`（经授权既有实际业务）、`controlled`（隔离虚构业务样例）、`synthetic`（独立规模集）。business 与 controlled 发布都必须有真实有效 owner_user_id；本版 synthetic 仅离线多主体实验，manifest.scope=offline_multi_subject、owner_user_id=null，**禁止导入本人查询库／API**。合成 subject_id 不冒用业务用户ID。

首版计划新增2表，均为**已批准设计，尚未实施**：

| 实体 | 最小字段与约束 | 用途 |
| --- | --- | --- |
| analytics_batches | batch_id CHAR(36) PK；owner_user_id FK users.id NOT NULL；周期、时区、cutoff；schema/metric/rule版本；dataset_kind；state；input_counts/quality/topic_summary JSON；artifact_ref；created_at/published_at；索引(owner_user_id,state,source_cutoff,batch_id) | 元数据和固定白名单专题汇总；topic_summary不是任意模型输出 |
| analytics_daily_metrics | batch_id FK；metric_date DATE；records/known_minutes/known_duration_count/missing_duration_count/known_zero_count；来源计数；task_total/completed/cancelled/overdue_unfinished；cohort/revised/confirmed计数；PK(batch_id,metric_date) | 每日同一快照结果，比例由准确分子分母生成 |

不新增行级提交明细数据库表；可追溯 DWD／专题事实文件留在受控批次目录。topic_summary 固定为第3节的群组、状态、比例和首反馈分布，响应最大90日，每日最多90行；质量输出只含安全错误码和计数。

### 5.2 状态与发布

文件状态 prepared→computed→validated，任何校验失败→failed。S05 导入先创建 prepared 批次；只有通过版本／类型／质量／归属验证，才在一次短事务内写入日汇总、专题汇总并置 completed。中途异常回滚所有结果行，另行安全记录 failed。不可把半成品作为上一成功批次。

completed 行与文件不可覆盖；同一 batch_id、相同结果重放 no-op，内容不同返回冲突；需要重算新建 batch_id。失败新批次不影响旧成功结果。清理仅限本次隔离虚构主体与未完成批次，已完成批次不由普通界面删除。

### 5.3 新只读接口与示例

拟新增2个 GET，不改现有 statistics／learning-reports：

- `GET /api/v1/offline-analytics/batches?dataset_kind=business&page=1&page_size=20`：仅当前用户 completed；page_size 1–50；按 source_cutoff DESC,batch_id DESC；可按周期筛选，筛选只挑匹配批次，不混算不同窗口。
- `GET /api/v1/offline-analytics/batches/{batch_id}`：返回同批元信息、daily、topic_summary、quality；owner 来自认证，客户端不能传 owner_user_id 改范围。

未登录401；不存在、非本人、未完成统一404；列表无结果200空数组。空 completed 批次仍先校验 owner；管理员身份不自动读取别人分析。synthetic 不进入这两个接口。查询／切图／刷新不启动 Spark、模型或业务写入。

```json
{
  "batch_id": "11111111-1111-4111-8111-111111111111",
  "dataset_kind": "controlled",
  "schema_version": "scholarhub-source-1.0",
  "metric_version": "learning-process-1.0",
  "source_cutoff": "2026-10-03T16:00:00Z",
  "business_timezone": "Asia/Shanghai",
  "topic_summary": {
    "cohort_count": 3,
    "revised_count": 1,
    "confirmed_count": 2,
    "confirmation_rate": {"numerator": 2, "denominator": 3, "percent": "66.666667"}
  }
}
```

这是响应片段；完整固定数字、每日行、质量断言见样例。前端一次选择并固定 batch_id，所有图表和解释同批；失败保留旧批次并显示其 cutoff；未知 metric_version 显示不支持并保留可读旧批次，不静默改口径。登录切换清理本人缓存，旧响应不得覆盖新账号。

## 6 固定答案与规模实验

[分析固定样例与独立答案](../阶段报告/AI大数据改造/V2/S01-分析固定样例与独立答案.json)包含 D00–D16 共17项，输入变化按每次全新深拷贝基准应用；D00核对完整结果，其余核对明确断言。期望值由设计时手算和独立规则给出，不从 Spark 运行结果反填。

D00 群组只有701、702、703：701为V1退回后V2通过，702首次提交待评，703首次即通过。首次反馈分别60分钟、无反馈、30分钟。记录归一化后每日分钟为30／45／0，记录数1／2／2；任务每日总数1／1／2，完成1／1／0。统计按快照而非历史日终；首次正确不被迫制造重提。

边界覆盖完全重复、冲突、主键缺失、跨日、伪来源、修改、删除、全空、无任务、全未知时长、仅取消、199/200、悬空关联、发布不可覆盖、空批次越权、cutoff右边界及教学记录删除。数据正确性在 S04 实跑；发布／权限规则在 S05 验证，S06完成真实全链与初步规模。

### 独立规模集

- 固定生成种子 `20261020`，不写业务库。三档唯一学习记录数 N=10,000／100,000／1,000,000；主体数100／1,000／10,000；任务数N/4，提交群组数N/100。所有主体是合成ID。
- 业务日固定2026-10-01至10-30，cutoff=2026-10-30T16:00:00Z；同种子、同生成器版本保留固定输入。分钟：20%未知、10%已知零、70%整数1–120；另复制2%完全重复记录。教师群组30%首次确认、30%修订后确认、20%退回待修改、20%待评；时间顺序合法。任务50%完成、25%待办、15%进行中、10%取消，按固定种子分配。小数人数按最大余数分配，余数并列按枚举顺序，避免实际分布漂移。
- 冲突／非法类型等拒绝样例另放 dirty 集，不能混入应发布的主性能集后悄悄删除。生成器和输入清单于 S03 交付，S01不生成规模文件。
- 本轮只读硬件信息：Windows内存约15.8GiB、20逻辑处理器，WSL MemTotal约7.65GiB。计划 `local[2]`、driver 2GiB、shuffle分区8，参数在实际命令留存，不改全局配置。先1万和10万；100万为有条件扩展，10万三轮稳定且峰值低于WSL内存60%、单轮不超过120秒时再做。资源不足保留失败和实际完成档，不冒称已达到百万。
- 每档记录全部源文件字节／行数、主体数、分区数、输出核对值、版本、硬件、启动／读取／清洗／关联／聚合／发布耗时。进程冷启动3轮，复用同一JVM预热1轮后测3轮；不主动清OS缓存，称“进程冷启动”，不称磁盘冷缓存。温热运行不额外缓存DataFrame，若改缓存另记方法，不能混用。
- Python标准库基线读取同份JSONL、采用相同键／群组／时间／质量规则；核对全部整数、分子分母与固定精度结果一致，再比较中位数及原始值。Python冷／热定义对应其进程生命周期，Spark启动成本单列；不承诺Spark更快。RSS用现有OS工具按1秒采样Python和本地JVM，注明采样峰值限制，不安装监控依赖。

## 7 最小 AI 模板与质量契约 B

固定 `python-learning-csv / 1.0`，函数为 `summarize_records(csv_text: str) -> dict`。输入必需列 record_id、duration_minutes，已命名额外列忽略；语法良好CSV，record_id为int可解析且>0；空白分钟为未知，非空为0–1440整数；每行独立、不要求跨行去重。非法行计数；缺表头抛ValueError；空白物理行按CSV解析忽略。

返回 record_count、known_duration_count、known_minutes、missing_duration_count、invalid_count 五个整数。空有效集也保留完整字段。函数无文件／网络／任意代码执行，学生在本人环境运行，平台仅静态评审。参考代码是评分材料，不自动展示给学生，也不在平台执行。

已有提示、讲解、静态评审来自 backend/app/workflow/agents.py、schemas.py 和现有 BaseAgent／AIClient／Provider。当前 answer_review 的 issues 是文本列表，不能据此假装已有 criterion_id：B 新增窄的实践评审 Schema，绑定 C01–C06 与 issue_type，复用底层消息、Provider和校验能力；**旧 answer_review Schema 与 WorkflowRun API 保持兼容**。

完整模板、7个固定输出向量、16个静态案例和参考标注见[AI评价案例](../阶段报告/AI大数据改造/V2/S01-AI固定模板与评价案例.json)。C01表头、C02解析／行有效性、C03计数／NULL零、C04累加、C05空集、C06纯函数。计分单位为(case_id,criterion_id)；上游行分类错误不在每个下游公式重复计算。issue_type保留具体原因。

16例为正确4、错误9、信息不足3；已知判定单元78，其中真实问题9、已知正确69，另18个未知单元。实际模型只看到任务、验收项、该例代码／声明和指定公开输出向量，不发送参考标签、参考代码、评分阈值或其他案例。

### S08 准入阈值

全部条件同时满足：问题命中≥8/9、漏报≤1/9；精确率≥0.80；误报FP/69≤0.05（整数最多3，且同时满足精确率）；错误通过0/9；信息不足误通过0/3且3/3识别信息不足；正确确认≥3/4；错误例中≥8/9反馈可执行性评分≥2，9例平均≥2；无无效响应及无依据的确定判断。精确率分母0为不可评分，不能当100%。

可执行性0–3分标准、AI裁判提示词、校准样例与原始记录在[评价评分表](../阶段报告/AI大数据改造/V2/S01-评价评分表.md)。按用户本次指令取消R1／R2人工双评前置，采用“固定规则核对＋J1独立AI裁判辅助评分”。数值与分母、响应结构、criterion集合和overall对照由离线规则计算；J1核对问题证据是否支持指定criterion，并评价反馈可执行性，不得重写冻结参考标签、期望答案或改变实际数字。S06专题解释也由J1按既定4项0–2分评分，仍要求≥6/8且不作因果／能力夸大。

J1默认选与被测模型不同的精确model_id，使用全新评分上下文，隐藏被测厂商与模型名，仅提供单例冻结参考、代码材料、待评分响应和评分规则。不同模型并不保证统计独立；若只能同型号评分，结果标“同模型辅助诊断”，不报独立裁判评价。数据与响应都是待评材料，其内部指令不得执行；仍不运行学生代码。先用G01–G03校准评分器，要求3/3匹配冻结得分／弃权预期；未匹配则记录评分器未通过并停止本轮评分，不反复调提示追求通过。J1遇到材料不足、证据冲突或无效输出时保留abstain／invalid和原始材料，不转成通过；未解决项使本轮辅助评价未完成，不要求再寻找第二个人。

保留原16例、78个已知／18个未知判定单元与全部数值阈值。TP／FN／FP由冻结标签和结构化判断计算；原先要求的“正确指出”还需J1确认引用证据成立。漏报的可执行性仍按0；裁判未能给出有效分数则记未评分，不从9例分母剔除。全部规则与AI裁判辅助门槛满足后，结论写“固定案例规则校验与AI裁判辅助评价通过”，不表述为人工双评、教师认可或真实教学有效性。

本轮真实模型调用／费用授权均为0。S08预算方案修订为最多35次Provider尝试：被测模型16次（每次输出≤1500tokens），J1校准3次与正式评分16次（每次输出≤1200tokens），均禁自动重试。S06专题解释另拟J1评分1次，不挪用S08额度；合计方案上限36次，**尚未授权实际调用**。需分别明确两类模型的provider、精确model_id、输入许可和合计货币上限后才运行；失败计入相应额度，不选择性换例或隐去评分器失败。工程Mock不能代替质量，产品演示额外调用另计。

## 8 会话 状态 版本与最小持久化 B

实践会话独立于旧 WorkflowRun，只支持固定模板两步：understand（理解输入与验收）→implement（提交实现并静态反馈）。首次实现正确后即可确认完成；重提只是恢复支线。

| 会话状态 | 允许动作／后继 |
| --- | --- |
| ready | start→running，保存模板与Context版本快照 |
| running | 只在一次有界模型操作期间使用；成功→waiting_confirmation或waiting_submission/revision；失败→failed |
| waiting_submission | 提交不可覆盖尝试；review→running |
| waiting_revision | 新attempt_no重新提交；不修改旧尝试；review→running |
| waiting_confirmation | understand的自我确认→waiting_submission；implement的有效评审后本人确认→completed |
| failed | continue按原模板／尝试／Context版本重试明确操作，不冒充成功 |
| cancelled | 保存取消事件；resume恢复到安全等待点，不自动重复旧模型调用 |
| completed | 只读；重新练习创建新会话，不改旧完成证据 |

Context变化不覆盖旧会话绑定。模型开始前以短事务准备 operation_id、版本和状态后提交；远程等待无数据库事务。提交结果重新校验 owner、session revision、attempt版本和operation_id；取消、旧版本或新操作获胜时，迟到响应不得覆盖。恢复返回等待点，由用户明确继续。

项目Context后来更新时，旧会话仍使用原始白名单快照，界面明确显示绑定旧版本；用户可继续原任务或新建会话，不把新Context静默灌入旧尝试。结果核对的是本次绑定版本，不把旧反馈写入新的attempt，也不借实践评审回写ProjectContext。

拟新增3个会话实体：

| 实体 | 必需字段／约束 |
| --- | --- |
| practice_sessions | UUID PK；owner_user_id、project_id FK；template_id/version；context_version、白名单context_snapshot；current_step_key；status、revision；active_operation_id、active_action、active_ai_request_id nullable；step_outputs仅保存两步结果引用；created_at/updated_at；每次动作expected_revision |
| practice_attempts | UUID PK；session_id FK；step_key、attempt_no、request_key；code_text≤12000字符、declared_output≤8KiB、self_statement；status、operation_id、ai_request_id FK nullable、review_schema_version、反馈JSON、时间；UNIQUE(session_id,step_key,attempt_no)和UNIQUE(session_id,request_key) |
| practice_events | UUID PK；session_id FK、attempt_id FK nullable；event_key、event_type、criterion_id、issue_type、confirmation_kind、occurred_at、白名单action_payload；UNIQUE(session_id,event_key)；不保存代码／教师评语／原始Prompt正文 |

尝试的提交载荷不可修改；运行状态和已绑定反馈可在受控事务中更新，不把整行称为永久不变。事件生产在S07/S08随真实动作上线：session_started、attempt_submitted、review_started/finished/failed、criterion_issue、step_confirmed、session_cancelled/resumed/completed。root event_key由合法request_key加固定后缀生成，逐criterion事件追加固定C01–C06后缀；NULL不用于唯一键。相同请求不同载荷冲突，相同请求重放已有结果。

模型静态判断、输出值匹配、自我声明、教师认可分栏。固定输出匹配只说明“提交的输出值与样例一致”，不表示服务器执行代码；AI pass不等于教师通过。教师认可只来自现有可信Feedback或另有真实授权流程，本版实践页默认“未提供”，学生不能自填teacher通过。所有代码仅供私有静态评审，不进入分析导出。

implement完成条件为：当前attempt已提交代码，T01/T04的声明输出与服务端固定向量一致，本次静态评审overall=pass且C01–C06均有有效判定，随后本人确认。insufficient不允许自动通关。这里只表示本次流程门槛，不能声称服务器运行或教师确认。取消后恢复状态由current_step_key和最新已绑定attempt／评审推导；迟到评审不能改变取消状态，恢复也不会自动重复模型操作。

新会话锁序遵守既有Project父锁：Project→PracticeSession→PracticeAttempt→Event；多行按ID。Context更新仍按既有Project→Workflow→Run/图的相对锁序，不反向持Practice锁再取Project。持锁只覆盖本地验证／保存，模型与人工等待均先提交。当前迁移为独立增量SQL与受控apply脚本；新迁移只新增表／索引／必要FK，不改旧迁移，不自动执行DDL。

拟新增5个会话接口：

1. POST `/api/v1/projects/{project_id}/practice-sessions`，body含template_id/version、expected_context_version、request_key。
2. GET `/api/v1/projects/{project_id}/practice-sessions`，本人分页历史。
3. GET `/api/v1/practice-sessions/{session_id}`，含绑定版本、步骤和尝试；不按客户端owner查询。
4. POST `/api/v1/practice-sessions/{session_id}/attempts`，含expected_revision、step_key、request_key、code、declared_output、self_statement。
5. POST `/api/v1/practice-sessions/{session_id}/actions`，仅允许固定start/hint/explain/review/continue/cancel/resume/confirm，含expected_revision、attempt_id和request_key；不是通用节点调度API。

非法输入422、未登录401、非本人／不存在404、版本／重放载荷冲突409。hint/explain/review是明确模型触发；GET、刷新、确认、取消和恢复不自动调用模型。每次最多1个模型操作，超时沿用现有Provider上限，失败保留精确状态。

拟新增提交请求片段如下，未实现或执行；T01/T04的值由服务端固定向量核对，不能由客户端提交“期望答案”替换：

```json
{
  "expected_revision": 4,
  "step_key": "implement",
  "request_key": "22222222-2222-4222-8222-222222222222",
  "code": "学生提交的完整函数文本",
  "declared_output": {
    "T01": {"record_count": 3, "known_duration_count": 2, "known_minutes": 30, "missing_duration_count": 1, "invalid_count": 1},
    "T04": {"record_count": 1, "known_duration_count": 1, "known_minutes": 1440, "missing_duration_count": 0, "invalid_count": 4}
  },
  "self_statement": true
}
```

保存后返回attempt_id、attempt_no、session_revision，静态review另由actions明确触发。响应证据分为self_statement、submitted_output_match、ai_static_review、teacher_confirmation；最后一项默认null，前三项不能填充它。确认请求必须绑定当前attempt_id和expected_revision。

## 9 页面 新事件与建议应用 B

项目准备维护目标、已定技术、材料与Context版本；实践工作台组织当前任务、尝试与反馈；本人数据页解释已经发布批次。沿用现有Campus Studio、ECharts及WorkflowExecutionPanel／WorkflowNodeResultContent；旧项目AI路由、工作流历史和高级画布兼容，不重画整站。

路由固定为沿用 `/projects/:id/ai` 承担准备、新增 `/projects/:id/practice` 承担实践、新增 `/offline-analytics` 承担本人离线分析；`/workflows/:id` 保留高级编辑与历史结果。A新增OfflineAnalyticsView及对应api/types，B新增PracticeWorkbenchView并收口ProjectAIWorkspaceView职责，不另建第二套图表或报告系统。

S03–S06的source-1.0不包含不存在的practice字段。S10按批准的新source-2.0／metric-2.0增加会话、尝试和事件白名单，保留criterion_id/issue_type/模板版本、会话群组及确认来源；覆盖起点取事件生产实际启用时间。统计取消／未结束使用同一快照的会话状态，事件表达发生顺序；不补造上线前事件，不混算不同模板／版本，不改完成旧批次。旧metric-1.0结果继续可读。

第一条建议规则 B-R1 固定为：同一会话同一criterion在至少两次不同已评尝试中仍有同issue_type，且当前未确认解决时，提示补一个对应边界样例。首次正确不触发；数据不足不推断能力。建议绑定batch_id、cutoff、metric_version、template_version、session/attempt/criterion来源，AI只能解释确定事实，不能改数字或自动改流程。

建议采用需要一次性幂等映射，拟新增第4个B表 `practice_recommendation_applications`：id、owner_user_id FK、batch_id FK、candidate_key、request_key、request_payload白名单JSON、task_id FK、created_at；UNIQUE(owner_user_id,batch_id,candidate_key)和UNIQUE(owner_user_id,request_key)。candidate_key由规则、会话、criterion、issue_type和模板版本的规范元组构成，不新加哈希机制。request_payload保留本次审阅的标题／日期／项目等原值，重复请求比较原载荷，不能用后来可编辑的任务值判断重放。

拟新增第6个B接口 POST `/api/v1/offline-analytics/batches/{batch_id}/recommendation-applications`，body为candidate_key、expected_metric_version、request_key及用户审阅后的task标题／日期／本人项目。服务端重新计算候选并核对当前来源／版本，同一任务与映射一次事务保存；重放返回同task，越权／旧版本不留下半个任务。首版只创建未关联计划的个人任务，不调整既有计划集合。

复用现有LearningService输入／归属验证，增加一个窄的create_task_from_recommendation用例及Repository原子保存方法；不能直接在外层调用会自行commit的旧create_task再补映射。普通任务创建API不变；锁顺序为批次→建议应用／新任务，不持Practice锁；若以后允许加入计划，需另列Plan→Task一致性影响再批准。

## 10 确切变更与分段批准

| 组 | 拟修改范围与影响 | 兼容性／依赖／用量 | 状态 |
| --- | --- | --- | --- |
| A 大数据核心 | analytics/源码与小样本、backend只读导出／受控导入脚本、2张analytics表及独立增量迁移、2个GET、本人离线分析页与DTO | 复用WSL PySpark及Python标准库／现有ORM，无新增第三方依赖；现有表和API不变；无模型调用 | 已批准本版设计，逐阶段实施 |
| B 最小AI联合 | 3张practice表＋1张建议应用映射表、6个新POST/GET、固定模板与窄评审Schema、两页职责收口、S10版本化事件分析、LearningService窄原子用例 | 不改旧WorkflowRun语义／answer_review格式；复用Provider，无新编排依赖；真实调用另有预算授权 | 已批准本版设计，逐阶段实施 |
| C 选做 | 仅草案／第二模板两个可分别选择的方向 | 未冻结实体或接口，不设计模板市场；每项另给具体变更后批准 | 未选择，默认跳过 |

S01批准只覆盖本版明确列项；同一范围后续不重复索取设计批准，但仍需用户逐阶段指令。隔离库具体名称和初始状态、师生数据范围、真实模型／输入／费用、安装、凭证和额外公开部署仍须对应明确授权；新增字段、表、接口或改变质量门槛必须列差异重新确认。不得自行把确认记录改成“已批准”。

## 11 周门槛 缩减与版本化验收

| 时点／阶段 | 必须看到 | 失败时缩减／停止 |
| --- | --- | --- |
| 第1周 S01/S02 | 本契约用户确认、固定独立答案；授权隔离来源链可产生正确样例 | 只修归属、状态、关系和抽取阻塞，不扩社区／课程 |
| 第2周 S03/S04 | 一致性快照、显式Schema、真实Spark与固定答案逐项一致 | 停在正确性，不画假图；冻结全部选做 |
| 第3周 S05/S06 | 完成批次、空批次权限、真实本人API／浏览器、主专题和1万／10万初步实验 | 先保数据闭环；规模失败记录原因，不降低事实／权限门槛 |
| 第3至4周 S07/S08 | 最小会话绑定／恢复；16例真实模型质量按冻结阈值验收 | 无预算或质量不过则AI质量未验收，不能由Fake或界面代替 |
| 第4至5周 S09/S10 | 两页真实接入、事件起点可追溯、建议确认只建一次任务 | 砍自由草案、第二模板、复杂流程编辑、过多图表；保留最小联合链 |
| 第5至6周 S12/S13 | 扩大／复验既有实验、论文主张与证据、8–12分钟演示 | 不新增功能；未完项明确列出，S12不是首次有效性验证 |

验收矩阵版本固定 `V2-S01-r2`（数据与案例继承r1，评分方式按r2）：A-DATA（D00–D12/D15/D16，S04）、A-PUBLISH（D13/D14，S05）、A-E2E（同批真实链和专题解释，S06）、A-SCALE（独立规模与同口径基线，S06先跑/S12复验）、B-ENGINE（版本、等待、首次正确、修改恢复、取消迟到、幂等，S07/S08）、B-QUALITY（Q01–Q16，S08）、B-JOINT（新事件／建议一次应用，S10）、C-OPTION（未选不算失败）。评分表中实际结果初始均为未运行。

没有正式任务书时以可复现技术案例提交，不宣称满足未确认校方算法／集群硬指标。S11始终让位于实验和论文。A/B的r1范围、分析口径、样例与原数值门槛继续有效；r2依据用户指令改用AI评分，人工评分人员不再是前置。评分器型号、输入许可和费用在实际评价前明确，不阻塞S02来源核验。本次不启动S02或任何业务迁移。
