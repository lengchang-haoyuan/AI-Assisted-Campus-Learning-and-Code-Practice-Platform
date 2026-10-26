# S06 judge-r4 真实评价结果

**S06完整验收通过：judge-r4校准3/3，正式解释四维2/2/2/2，共8/8；因果/能力夸大=false，无未解决无效或正式弃权。** 原工程/数据/真实浏览器/两档实验引用既有证据，本轮只修评价说明并完成真实J1，不启动S07。

## 修复与授权

用户请求解决字段歧义后，先完成[judge-r4修复准备](../../S06-J1准备/20261021-judge-r4/README.md)：r3原文作为完整前缀，仅追加“评价候选反馈主张是否得到支持”的语义，禁止用裁判自行发现的代码缺陷替错误反馈补证；缺反馈、null和各维独立判定沿用原规则。没有写入G01–G03具体答案或改输入/解释/阈值/验证器。

33项离线核对和一次有限语义审阅后，用户明确“追加2次额度，执行新轮3＋1”；S06累计上限从5提高为7，DeepSeek Flash、费用不限沿用。见[授权](authorization.json)。此前已用3次计入，当前新轮最多4次、校准失败停止、重试0、不推进S07。

[参数](parameters.json)：deepseek/deepseek-flash、judge-r4、temperature0、max_tokens1200、json_object、thinking disabled、总超时60秒、应用/transport重试0、无工具/重定向/历史上下文。除系统语义说明与累计预算外沿用原运行方式；现有Provider/AIClient及密钥认证复用，凭证未打印或保存，产品源码、API/数据库、依赖、全站配置、旧ODS/Spark/批次均未修改。

## 真实校准与正式结果

执行时间：2026-10-21 22:19:42–22:19:46 +08:00。四次均HTTP200/finish_reason=stop、每例恰好一次POST，无重试或额外探测请求。

| 用例 | 实际关键字段 | 冻结预期匹配 | 原始证据 |
| --- | --- | --- | --- |
| G01 | scored / 3 / C01证据true / unsupported=false | 全匹配 | [响应](raw/G01-response.json)、[检查](raw/G01-validation.json) |
| G02 | scored / 0 / C01证据false / unsupported=true | 全匹配 | [响应](raw/G02-response.json)、[解析](raw/G02-parsed.json)、[检查](raw/G02-validation.json) |
| G03 | abstain / 分数null / 证据null / unsupported=null | 全匹配 | [响应](raw/G03-response.json)、[检查](raw/G03-validation.json) |

G02这次引用候选反馈的具体错误主张，理由明确说明其与reference相反，字段false符合冻结预期。G03是预定的材料缺失校准，预期弃权正确匹配，不是正式评价遗留弃权。旧r2/r3原始失败及消耗保留，不转换旧结果。

正式artifact=`S06-analysis-b96ea63e-v1`，文本版本1.0；主批仍b96ea63e-419e-4293-b724-d1ce59bd85ba、90分钟/5记录/缺2/任务2比4/确认2比3，边界仍3217db64-1302-4722-a483-c3b1ad7b980f、199比200/逾期1。正式输入与原准备完全一致，仅system更新judge-r4。

| 正式维度 | J1分数 |
| --- | ---: |
| 问题与群组 | 2 |
| 数字证据 | 2 |
| 模式与反例 | 2 |
| 结论边界 | 2 |
| 外部规则合计 | **8/8** |

status=scored，causal_or_ability_overclaim=false，四项原文quote可定位，结构/身份/引用有效，无无效字段或未解决弃权；通过冻结≥6/8门槛。见[实际请求](raw/analysis-request.json)、[原始响应](raw/analysis-response.json)、[解析正文](raw/analysis-parsed.json)、[规则检查](raw/analysis-validation.json)、[门槛汇总](rule-summary.json)。引用存在只证明可定位；评分按AI裁判辅助评价口径，不表示人工双评或真实教学效果。

## 用量与费用

| 范围 | 次数 | 输入 / 输出tokens | CNY核算 |
| --- | ---: | ---: | ---: |
| 旧judge-r2轮 | 1 | 1080 / 139 | 0.00163600 |
| 旧judge-r3轮 | 2 | 2953 / 250 | 0.00332580 |
| 本judge-r4轮 | 4 | 10169 / 663 | 0.00968500 |
| S06累计 | **7/7** | **14202 / 1052**，共15254 | **0.01464680** |

本轮G01/G02/G03/正式耗时1059/1253/608/1785ms，分别核算0.00185724/0.00140192/0.00120792/0.00521792元；[实际账本](ledger.json)保留原始usage和缓存拆分、参数、耗时、请求/响应及累计次数。按再次核实的[官方CNY空闲价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)用Decimal核算，不是账户扣款或发票确认；[pricing-basis.json](pricing-basis.json)保留依据。当前剩余已授权尝试0；失败未清零，角色未互借，原跨阶段方案含新增校准为39次，S08实际调用仍未授权。

## 检查与恢复

项目根实际运行本目录`run_evaluation.py`无参数预检exit0，随后加`--execute`exit0，完成3校准+1正式。**执行命令是历史记录，不可重跑**；已有账本会拒绝重复执行。默认预检不调用模型，每次Provider前检查本轮4/累计7并先记次。

[final-qa.json](final-qa.json)记录AST、消息Schema、准备prompt原样、原验证器/调用参数未变、四份请求与固定输入一致、原始响应规则复核、预算/费用重算、JSON/链接/差异/常见令牌模式检查。本轮没有因离线评价重跑历史后端30项、前端构建/类型、真实浏览器或Spark/规模实验；没有源记录重采/写库、重建ID8或覆盖90分钟历史。

本次校准在相同provider、精确服务模型版本、judge-r4原文、参数和校准材料不变时可供S08复用；别名可能对应后续升级，复用前核实模型版本与原响应fingerprint等配置证据。S08若被测模型同型号，仍按原契约标同模型辅助诊断，不能冒称独立裁判。复用不代表S08质量已验收或新增调用许可。

恢复从[任务交接](../../../../../任务交接.md)、[S06报告第13节](../../S06-完成报告.md#13-2026-10-21-judge-r4语义修复及完整s06通过)及本轮账本开始。S07原S06完整前置已满足，但本轮不启动；仍由用户明确下一阶段及必要隔离写入范围。没有自动提交、推送、发布或部署；历史失败、固定答案和所有既有未提交工作保留。
