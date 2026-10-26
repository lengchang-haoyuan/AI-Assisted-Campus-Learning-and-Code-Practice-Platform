# S06 judge-r3 新轮评价

日期：2026-10-21，Asia/Shanghai。**本轮已结束：G01校准匹配，G02证据有效性不匹配，停止G03和正式analysis。完整S06尚未通过，S07未启动。**

## 修改与授权

用户直接授权：“只修评分格式并形成judge-r3，追加1次校准额度，本阶段累计最多5次。新轮执行3次校准加1次正式评分，失败停止，不自动重试，不推进S07。”DeepSeek Flash、既定白名单输入和费用不限沿用；授权见[authorization.json](authorization.json)。

[judge-r3-system.txt](judge-r3-system.txt)原样保留judge-r2前缀，仅追加状态枚举、身份/字段/类型、不可评分null、原文引用与简短JSON格式要求，见[prompt-diff.md](prompt-diff.md)。没有加入校准expected，没有改四份固定输入、解释artifact、独立答案、评分规则/阈值、响应契约或验证器。旧r2提示词及原始status=ok失败保留在[旧轮](../20261021-deepseek-flash-r1/README.md)。

本轮仍为deepseek/deepseek-flash，temperature0、max_tokens1200、json_object、thinking disabled、60秒总超时，应用与HTTP transport重试均0，无工具/重定向，每例新上下文。复用现有Provider/AIClient，密钥只进认证，不打印/保存；全站默认model、环境配置、产品源码、数据库、依赖和既有ODS/Spark/发布/实验不改。具体见[参数](parameters.json)。

## 实际结果

运行时间：2026-10-21 22:04:32–22:04:35 +08:00。

| 用例 | 状态 / 分数 | 证据有效 / 无依据声明 | 冻结匹配 | 结果 |
| --- | --- | --- | --- | --- |
| G01 | scored / 3 | true / false | 全匹配；引用可定位 | 校准通过 |
| G02 | scored / 0 | **true** / true | evidence_valid应为**false**，其余预期匹配；引用可定位 | 校准失败，立即停止 |
| G03 | 未运行 | 未运行 | 未运行 | 没有发送 |
| 正式analysis | 未运行，总分null | 未运行 | 无3/3有效校准 | 没有发送 |

G02的响应字段、分值、状态与引用均有效，区别于旧轮的状态格式错误。它正确给出0分并识别编造执行，却引用学生代码缺表头分支说明“C01不通过”，把evidence_valid置true；冻结G02要求该错误候选反馈的证据无效false。这是实际语义判定与冻结预期不匹配，不能转换true或改expected来通过。引用存在只证明可定位，不代表支持了本次候选反馈。未超出本轮“只修格式”范围修改提示语义或再次调用。

原始证据：[G01响应](raw/G01-response.json)、[G01解析](raw/G01-parsed.json)、[G01检查](raw/G01-validation.json)、[G02响应](raw/G02-response.json)、[G02解析](raw/G02-parsed.json)、[G02检查](raw/G02-validation.json)、[规则汇总](rule-summary.json)。实际请求、每例输入和Provider解析也留在`raw/`，不含认证headers或密钥。

## 计次、tokens与费用

| 范围 | 尝试 | 输入 / 输出tokens | 核算费用CNY |
| --- | ---: | ---: | ---: |
| 旧轮judge-r2 | 1 | 1080 / 139 | 0.00163600 |
| 本轮judge-r3 | 2 | 2953 / 250 | 0.00332580 |
| S06累计 | **3/5** | **4033 / 389**，合计4422 | **0.00496180** |

本轮G01耗时1270ms、缓存命中128/未命中1350，费用0.00184456元；G02耗时1259ms、命中512/未命中963，费用0.00148124元。均HTTP200、finish_reason=stop，每例恰好1次POST，无自动重试或额外模型/余额请求。见[实际账本](ledger.json)。

费用以真实usage和再次查询的[官方CNY定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)计算：本次夜间每百万输入命中0.02元、未命中1元、输出4元，使用Decimal；不是账户扣款或发票核对。[pricing-basis.json](pricing-basis.json)保留依据。失败尝试仍计入，旧轮未清零。

新增1次校准额度后，S06累计校准最多4次、正式最多1次；实际累计校准3、正式0，未用校准1+正式1，共2次。本轮已停止，未用2次不允许自动重试/重校准。原跨阶段36方案相应成为37（含1次原失败），S08的16被测/16裁判不因本轮获实际调用许可，不借角色额度。

## 检查、停止与恢复

项目根实际命令：

```powershell
& .\backend\.venv\Scripts\python.exe -B -X utf8 '开发相关文档/阶段报告/AI大数据改造/V2/S06-J1运行/20261021-deepseek-flash-r2-judge-r3/run_evaluation.py'
& .\backend\.venv\Scripts\python.exe -B -X utf8 '开发相关文档/阶段报告/AI大数据改造/V2/S06-J1运行/20261021-deepseek-flash-r2-judge-r3/run_evaluation.py' --execute
```

预检exit0、无模型；实际执行exit0，表示按校准失败停止并落盘，不表示整组校准通过。上述执行命令仅用于记录，**不得重跑**；已有账本会拒绝重复执行。每次Provider前记次并检查本轮4/阶段累计5上限，默认无`--execute`只做本地检查。

[preflight.json](preflight.json)与[final-qa.json](final-qa.json)记录AST、消息Schema、r2原文前缀、验证器不变、实际请求→固定输入一致、原始响应→规则复核、累计预算/费用、JSON/链接/差异及常见令牌模式检查。这些是本轮离线检查；历史30后端、前端构建、真实浏览器及两档实验均只引用[原S06报告](../../S06-完成报告.md)，没有重跑。

当前整组校准未通过，不可供S08复用；正式artifact仍为`S06-analysis-b96ea63e-v1 / 1.0`，没有正式分数。恢复先读[任务交接](../../../../../任务交接.md)、本轮ledger及G02原始检查；新语义说明或新评价轮次需另明确范围，保留所有冻结预期及旧失败，不继续使用剩余2次。本轮仅新增本目录、追加原报告/索引/日志并更新同一交接；没有自动提交、推送、发布、部署或推进S07。
