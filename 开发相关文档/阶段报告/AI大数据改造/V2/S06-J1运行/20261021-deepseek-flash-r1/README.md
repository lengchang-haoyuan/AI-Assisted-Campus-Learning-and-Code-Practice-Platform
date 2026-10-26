# S06 J1 真实评价 r1

日期：2026-10-21，Asia/Shanghai。**本轮已结束：G01响应无效，校准未通过；正式专题未评分，完整S06仍未通过。**

## 授权与实际消耗

用户在本对话先回复“授权”，随后指定DeepSeek Flash，并明确“本轮费用不设上限，仍最多4次调用”。本轮许可涵盖准备目录的三份校准输入及一份正式analysis输入，校准不匹配即停止、无自动重试，不包含S07、数据写入、配置修改或其他模型角色。见[授权原话](authorization.json)。这是新许可；[准备版本](../../S06-J1准备/20261021-r1/README.md)的零调用/未运行文件仍作为历史保留。

| 项目 | 实际 |
| --- | --- |
| Provider / 请求model_id | deepseek / deepseek-flash |
| 返回model_id | deepseek-flash；原响应另保留system_fingerprint；官方查询时服务版本为DeepSeek-V4.1-Flash-1017，不能仅凭别名保证将来后端版本不变 |
| 运行区间 | 2026-10-21 21:51:10–21:51:11 +08:00 |
| 调用 | 1次G01校准，HTTP200，耗时1111ms；G02/G03/analysis均0次 |
| 用量 | 输入1080、输出139、合计1219tokens，缓存命中0/未命中1080 |
| 费用 | 按真实usage×官方当时CNY空闲价计算0.001636元；未读取账户余额或核对实际扣款 |
| 本轮剩余 | 次数上限4，已用1、未用3；本轮已因校准失败停止，不自动把未用次数当重试许可 |
| 配置 | judge-r2、temperature=0、max_tokens=1200、json_object、thinking=disabled、总超时60秒、max_retries=0、transport_retries=0、无工具、每次全新上下文 |

费用依据：[官方中文定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，空闲价每百万输入未命中1元、命中0.02元、输出4元。本次计算为`1080×1/1000000 + 139×4/1000000 = 0.001636 CNY`，仅为真实用量按公开价格的计算结果。精确配置、时间/用量和计次见[参数](parameters.json)、[账本](ledger.json)、[定价依据](pricing-basis.json)。

调用复用现有`DeepSeekProvider`与`AIClient`，只在此评价进程创建局部实例；项目已有密钥仅用于认证，没有写入请求材料、响应日志或聊天。全站旧默认`deepseek-v4-flash`、`.env`及其他运行配置没有修改。本轮采用官方当前API型号`deepseek-flash`，根据[官方模型更新](https://api-docs.deepseek.com/updates/)与[API参数文档](https://api-docs.deepseek.com/api/create-chat-completion/)在首次校准前将未决thinking固定为disabled，保持温度0有效；全轮没有中途调参。

## G01结果与停止原因

| 冻结检查 | 预期 | 原始返回 | 判定 |
| --- | --- | --- | --- |
| 当前case_id | G01 | G01 | 匹配 |
| status | scored | **ok** | **不匹配 / 非法枚举** |
| 可执行性 | 3 | 3 | 匹配，但不能补偿状态无效 |
| criterion_id | C01 | C01 | 匹配 |
| evidence_valid | true | true | 匹配 |
| unsupported_claim | false | false | 匹配 |
| quote | 可定位原文 | 缺表头分支及return {} | 当前输入中存在 |

`ok`不在冻结的`scored / abstain / invalid`集合，离线规则将本次有效状态判为`invalid`，G01校准未通过；没有把`ok`转换成`scored`。验证输出里由非法status产生的非空评分/布尔字段错误属于后续结构检查，不表示另有三次独立模型失败。3分是G01校准材料的可执行性分数，**不是S06专题得分**。

原始证据：[实际请求正文](raw/G01-request.json)、[本次输入](raw/G01-input.json)、[原始HTTP响应](raw/G01-response.json)、[Provider解析结果](raw/G01-provider-result.json)、[模型JSON正文](raw/G01-parsed.json)、[规则检查](raw/G01-validation.json)、[规则汇总](rule-summary.json)。请求材料不含headers或密钥；原始响应未发生秘密值替换。

当前judge-r2系统提示词列出status字段但没有展开合法枚举，动态输入也没有携带本地response-contract；这些都是实际发送材料的事实。本轮未改变提示词、输入、冻结预期或阈值以追求通过。结果只能说明该固定输入/提示词/模型组合没有通过本轮校准，尚不能给正式解释稿定分。

## 执行与本地检查

项目根目录执行：

```powershell
& .\backend\.venv\Scripts\python.exe -B -X utf8 '开发相关文档/阶段报告/AI大数据改造/V2/S06-J1运行/20261021-deepseek-flash-r1/run_evaluation.py'
& .\backend\.venv\Scripts\python.exe -B -X utf8 '开发相关文档/阶段报告/AI大数据改造/V2/S06-J1运行/20261021-deepseek-flash-r1/run_evaluation.py' --execute
```

首条为本地预检，未发模型；第二条为本次实际执行记录，**不能再次执行**。程序发现已有账本会拒绝重跑。执行退出0表示按校准失败规则停止并留证，不表示校准通过。请求前计次；HTTP hook记录恰好1次POST，不包含认证headers；无SDK/应用/transport自动重试，无额外余额或探测请求。

新增两个评价脚本的AST、离线请求Schema、输出JSON/本地链接/差异和令牌模式检查见[QA](final-qa.json)。[离线验证器](validate_j1_response.py)检查身份、精确字段/类型/枚举、分值范围、引用、冻结预期和正式总分；引用存在只证明可定位，不能单独证明语义正确。没有执行学生代码，没有业务测试、数据库、普通GET、Spark或规模实验。原工程/数据/浏览器/两档实验仅引用[原报告](../../S06-完成报告.md)。

## 恢复与下一步

当前无有效校准可供S08复用；正式analysis未运行、得分null，S07原前置未满足。本轮到此停止，剩余3次不自动重试、调参、替换模型或挪用S08额度；原36次方案中失败校准也计入，不能宣称尚未消耗。

恢复先读[持续交接](../../../../../任务交接.md)、本目录账本和原始G01。若用户要求新轮，应先明确输出格式说明的最小差异并形成新版本，再按新明确次数范围重新校准；保留本轮原始失败，不改G01–G03预期、分数阈值或旧准备artifact。完整新轮仍需3次校准+1次正式，不能将本轮未用3次直接表述为足够完成新轮。没有自动提交、推送、发布、部署或推进后续阶段。
