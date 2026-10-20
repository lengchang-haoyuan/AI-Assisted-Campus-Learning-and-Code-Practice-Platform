# ScholarHub 离线学习过程分析

截至 2026-10-20，V2-S01-r2 契约下 S03 快照、S04 真实 Spark 计算和 S05 分析发布已完成；S06 展示与初步实验待执行。当前数据链路是：

```text
现有业务 MySQL → 同连接一致性 ODS → PySpark DWD → Spark SQL ADS
                                                   ↓
                                  受控离线发布 → 分析批次与日表 → 本人只读 GET
```

这里是本机离线分析模块，沿用已安装的 WSL PySpark 4.2.0、Python 3.12.3、JDK 17；Windows 抽取和发布使用 backend/.venv Python 3.12.14。普通 GET 不启动 Spark、模型或发布器，应用服务也不会因导入此目录而自动运行离线任务。

## 当前可用能力

| 环节 | 实现与说明 |
| --- | --- |
| S03 快照 | 10 表 71 字段核心白名单，同连接 REPEATABLE READ 一致性导出；AI 请求另存 9 字段辅助元数据；[报告](../开发相关文档/阶段报告/AI大数据改造/V2/S03-完成报告.md) |
| S04 计算 | [spark_job.py](spark_job.py) 和 [learning_process.sql](learning_process.sql)，输出 DWD Parquet、ADS JSON、质量与谱系；[运行和字典](S04.md) |
| S05 准备 | [prepare_publication.py](prepare_publication.py) 离线读取已完成 DWD，补齐契约中的日零值／来源分项，与原 ADS 核对后形成发布输入 |
| S05 发布 | [publish_analytics.py](../backend/scripts/publish_analytics.py) 经[受控加载器](../backend/app/services/analytics_artifacts.py)和发布服务写入分析存储；[发布与接口说明](../开发相关文档/阶段报告/AI大数据改造/V2/S05-发布与接口契约.md) |
| S05 查询 | [两个 GET](../backend/app/api/v1/analytics.py)经现有认证，只读取本人 completed 批次；[S06 固定输入](../开发相关文档/阶段报告/AI大数据改造/V2/S05-S06交接索引.json) |

三类指标为记录分钟与活跃日、任务完成与逾期未完、提交修订与教师确认进展。NULL 时长保留缺失含义；任务取消仍纳入分母；199/200 保持 99.5%；可信教学来源必须由 ACCEPT Feedback、版本、记录和主体关系证明，JSON 声明不能决定来源。

当前仅专用隔离库完成两张分析表迁移，真实结构核对为 36 表／83 外键，原业务库和服务配置没有迁移。两个正式发布批次均为 `controlled`，来自真实 Spark 主／边界计算；1 万记录／100 主体的 `synthetic` 规模集只离线实验，不发布到本人查询库。S05 的 47 项通过是定向后端检查，页面与浏览器接入留在 S06。

## S03 快照与实验输入

以下保留 S03 的抽取、生成与消费方法；已有完成产物直接复用，重新抽取或生成应使用新的标识和目录。

### 入口

- `backend/scripts/export_ods_snapshot.py`：现有 10 表、71 字段的同连接只读一致性导出；另有经 S03 明确批准的 9 字段 AI 辅助文件。
- `analytics/snapshot_files.py`：临时目录、完成发布、不可覆盖和读取完整性检查。
- `analytics/prepare_samples.py`：物化 S01 的 D00–D16、M01 多主体样例及固定种子 1 万记录档。
- `analytics/fixture_answers.py`：独立 Python 核算参考；S04 的 Spark 作业应独立实现，不能将这里的答案直接当计算输出。
- `backend/tests/test_ods_snapshot.py`：窗口、来源关系、冻结答案、文件失败与覆盖边界测试。

无需新增第三方依赖。使用现有 `backend/.venv`。Windows 该环境没有 tzdata，本轮从已运行的 WSL 只读使用 IANA 时区文件；环境变量只对当前 PowerShell 进程和子进程有效。WSL Linux 原生 Python 可直接使用系统 zoneinfo。

```powershell
# 仓库根目录；先确认 WSL 的时区文件可读。
$env:PYTHONTZPATH='\\wsl.localhost\Ubuntu-24.04\usr\share\zoneinfo'
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.export_ods_snapshot `
  --database scholarhub_l4_s02_20261020 --owner 3 `
  --start 2026-10-19 --end 2026-10-20 `
  --output '../开发相关文档/阶段报告/AI大数据改造/V2/S03-ODS' `
  --include-ai-aux
```

省略 `--snapshot-id` 会生成新 ID。不能使用已存在的完成 ID。该 CLI 限定本轮确认的本机隔离库与主体 3/4；凭证使用既有配置在进程内解析，不输出连接字符串。扩展目标必须先确认来源授权和 dataset_kind。

生成样本需使用**不存在的新输出目录**，以免覆盖冻结材料：

```powershell
# 仓库根目录
$env:PYTHONTZPATH='\\wsl.localhost\Ubuntu-24.04\usr\share\zoneinfo'
.\backend\.venv\Scripts\python.exe -B -X utf8 -m analytics.prepare_samples --output '<新的隔离输出目录>'
```

支持的生成器参数为固定种子 20261020，N=10000/100000/1000000；CLI 本阶段只生成 10000 档，其余档未运行。合成 ID 属于离线命名空间，禁止导入本人查询库。

### 消费边界

固定输入入口见[阶段输入索引](../开发相关文档/阶段报告/AI大数据改造/V2/S03-输入索引.json)，主快照是 `s03-owner3-restored`。

只有 `snapshots/<snapshot_id>/manifest.json` 中 `extraction_status=complete` 的目录可读，状态 `prepared` 表示已完成 ODS 抽取，尚未经 Spark 计算。`.incomplete` 下即使存在部分文件也不可消费。读取端核对文件集合中的行数和字节数；这是写入协议的不可覆盖保证，不声称防止管理员手工篡改。

JSONL 文件采用 UTF-8、LF。DATETIME 使用 UTC、Z 后缀、保留微秒；DATE 原值不偏移；NULL 不替换为零。JSON 整数保持精度，所有源 ID 范围限于 1..2^63−1。

个人窗口以 Asia/Shanghai 起始日零点至结束日次日零点转换成 UTC，左闭右开。记录按发生时间、任务按 DATE、提交群组按 V1 时间进入；相关反馈和窗口外必要父链保留为关系闭包。聚合前必须再次按 owner 和窗口选择事实，不能把依赖闭包全部计入指标。

AI 辅助字段：id、user_id、project_id、status、requested_at、finished_at、prompt_tokens、completion_tokens、latency_ms。独立版本 `ai-request-aux-1.0`；不改变核心 `scholarhub-source-1.0` 和指标版本。没有 provider/model/正文/错误文本；当前源是 S02 Fake 请求，运行来源在 manifest 和报告中说明。

### 真实验证脚本

[S03 证据目录](../开发相关文档/阶段报告/AI大数据改造/V2/S03-验证证据/)保留实际验证脚本和原始日志。脚本会创建临时记录，因此**不要把查阅证据当作重跑授权**。本轮允许的两条记录已清理，重新执行需要新的写入范围确认。

## S04 Spark 复跑与完成协议

完整命令、显式 Schema、DWD／ADS 字典和独立核对方法见 [S04 说明](S04.md)。作业入口必须给固定 `--input`、新的 `--output` 和未成功使用的 `--job-id`。当前配置是 local[2]、driver 2 GiB、shuffle 分区 8；它是本机实验，没有部署集群。

只消费 `extraction_status=complete` 的 ODS。成功任务写入 `jobs/<job_id>`，保留 snapshot_id、窗口、source_cutoff 和规则版本；`.incomplete` 与失败目录不可发布。完成任务不覆盖，独立验收放在完成目录之外。S05 同时核对 computed、质量对账和独立验收结果，不因存在 Parquet 就接受发布。

S04 已用真实 Spark 运行固定小样本、多主体和 1 万记录档，并与独立 Python 对照；[计算报告](../开发相关文档/阶段报告/AI大数据改造/V2/S04-完成报告.md)记录实际输入、时间和资源边界。10 万／100 万档、重复冷／热实验和正式专题语言评分仍待后续，不能从一次运行推导通用性能优势或教学效果。

## S05 发布和本人查询

已准备的[主输入](../开发相关文档/阶段报告/AI大数据改造/V2/S05-发布输入/v2-controlled/payload.json)和[边界输入](../开发相关文档/阶段报告/AI大数据改造/V2/S05-发布输入/v1-boundary/payload.json)可直接复用。准备器只接受受控交接清单的两个 job，现有 sidecar 目录不允许覆盖；它需要 PySpark，但发布 CLI 只加载校验后的 JSON，不启动 Spark。

以下是当前已验证目标的迁移／发布命令，在 backend 目录执行；重放两个正式 job 返回既有批次。迁移在两表都存在时仅核对结构；部分结构存在时停止，不删除重建。命令不会修改 .env，连接凭证沿用现有配置在进程内解析。

```powershell
.venv/Scripts/python.exe -B -X utf8 -m scripts.apply_s05_analytics_migration --database scholarhub_l4_s02_20261020
.venv/Scripts/python.exe -B -X utf8 -m scripts.publish_analytics --database scholarhub_l4_s02_20261020 --job-id v2-controlled
.venv/Scripts/python.exe -B -X utf8 -m scripts.publish_analytics --database scholarhub_l4_s02_20261020 --job-id v1-boundary
```

| 正式来源 | 批次 ID | 核对结果 |
| --- | --- | --- |
| 主样本 v2-controlled／owner 3 | 77e12daa-c693-4c47-8ef8-e7c5b78b1395 | 4 记录，已知 75 分钟／缺失 2 条；任务 2/4；群组 3、修订 1、教师确认 2；2 日日汇总 |
| 边界 v1-boundary／owner 4 | b9378c01-70b2-4456-9d44-b579617375d1 | 任务 199/200=99.500000%；无记录和教学样本；1 日日汇总 |

两个 GET 复用当前登录凭证，user_id 由服务端取得：

```http
GET /api/v1/offline-analytics/batches?dataset_kind=controlled&page=1&page_size=20
GET /api/v1/offline-analytics/batches/77e12daa-c693-4c47-8ef8-e7c5b78b1395
```

列表默认 `dataset_kind=business`，当前该种类没有样例；受控演示须明确选择 controlled。可用周期筛选选择完整批次，详情不接受额外日期过滤。未登录 401，非本人、未完成或不存在批次 404，非法参数 422；管理员也不能越过本人范围。空批次仍先鉴权。列表 `empty_reason` 区分 no_completed_batch、no_matching_batch 和 page_empty。

响应含 batch_id、数据种类、时区、窗口、源截点、规则／指标版本及分子分母，所有图表应固定同一 batch_id。主样本业务期为上海 2026-10-19–20，source_cutoff 为 `2026-10-20T07:34:07.134833Z`，不因页面刷新而变成实时数据。旧 `/statistics` 继续表示业务实时聚合。

发布 prepared → completed 的日行与状态在同一事务完成；失败回滚，旧成功仍可读。成功批次同内容重放幂等，异内容冲突，不允许覆盖；双连接并发已验证。恢复方法及实际证据见 [S05 报告](../开发相关文档/阶段报告/AI大数据改造/V2/S05-完成报告.md)。

S05 共保留 11 批次／15 日行，其中仅上表两个是正式 Spark 交接来源，其他是权限或事务测试样例。接入应使用 [S06 交接索引](../开发相关文档/阶段报告/AI大数据改造/V2/S05-S06交接索引.json)指定 ID，不能把列表第一项当作主样本。验证脚本可能创建对象，不应为展示重新运行；业务服务指向原库时也不能直接假设新表已经存在。
