# S08真实评价r2：Flash被测提示r2 / Pro judge-r4

本轮源于用户在列明32次/2CNY及校准复用条件后明确回复“请你开始”。[授权](authorization.json)：deepseek-flash被测最多16次、deepseek-v4-pro正式J1最多16次，新增校准0次，合计最多32次、硬上限2元人民币。客户端/transport自动重试0；失败计数并停止，不能借旧轮次数或自动扩额。不写库、不执行学生代码、不推进S09，不提交/推送/部署。

固定输入仍取原Q01–Q16代码/声明/各自指定向量和原合成Context，J1单例可见冻结参考及本轮新候选，被测型号/provider等元数据不进入J1消息。被测只使用已完成本地检查的practice-review-r2，schema1.0；J1提示/参数/材料沿用judge-r4。精确值见[parameters](parameters.json)、[完整role](review-role-instruction.txt)。未改变任何冻结答案、阈值或分母。

新候选身份为`S08-Qxx-candidate-v2 / text_version=2.0`，新结果不得覆盖v1。`score_results_r2.py`相对原计分脚本仅适配v2身份/text版本及原J1模板路径，算法/门槛/分母完全保留；预检逐字比较这些允许差异之外的源文件，`validate_judge.py`为原文件原样副本。15项合成计分边界自检通过，Fake不是模型质量结果。

## 校准复用与停止

执行前重新核对原S08 Pro G01–G03的原始响应、冻结输入/预期、judge-r4原文、采样/输出/超时/重试参数和公开文档服务版本，3/3仍匹配，见[calibration-reuse](calibration-reuse.json)。没有复用S06 Flash校准，也不发送新校准请求。每个新Pro响应必须仍有服务fingerprint `a307abda487cd1b463329ccb945ce396`，否则停止本轮，不自动补校准。

[官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)于2026-10-23执行前再次核对，文档服务版本Flash-1017/Pro-0813和价格与准备时一致，见[pricing-basis](pricing-basis.json)。预算按峰价、输入全未命中预留：每次POST前先计次、按完整messages的UTF8字节+512余量及输出cap计最大费用并持久化。成功按真实usage同口径上界结算，失败保留预留；现有保守已用/预留加下一笔最大预留超过2元时，在POST前停止。缓存/夜间折扣不抵扣此口径，不能声称是账户扣款或余额。

18项离线执行器守卫通过，覆盖32次角色限制、2元门槛、零新增校准、服务fingerprint变化拒绝、请求前计次/预留、失败保留及已有证据拒绝重跑。16份被测请求的最大预留合计0.486384CNY；正式J1依赖新候选，逐次重算，不承诺2元必能覆盖完整最坏情形。

Provider/结构异常、正式J1弃权无效、校准不再可复用或预算不足停止后续；普通质量失误仍按固定顺序收齐全部16例，不修改提示、参数、答案或阈值追分。新轮结束按原规则给结论，不自动追加第二轮。

## 命令与恢复

默认只做本地预检，不读key、不请求模型或数据库：

```powershell
.\backend\.venv\Scripts\python.exe -B -X utf8 "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261023-flash-pro-r2/run_evaluation.py"
```

根agent审阅授权与预检后，本轮执行一次：

```powershell
.\backend\.venv\Scripts\python.exe -B -X utf8 "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261023-flash-pro-r2/run_evaluation.py" --execute
```

只有实际execute在记账后读取项目现有key用于进程认证；原始POST/body按inputs/raw/candidates/judges/validations分别保存，禁止保存认证headers。已有ledger或raw拒绝重发；进程中断先只读[ledger](ledger.json)，不能直接再执行收费命令。退出0表示采集完成，质量是否通过由规则/校准/账本共同认定。

本README的预备状态不等于执行结果；当前结果以最新账本为准。后续收口追加实际调用、usage/费用、评分与未完成项，并更新[原阶段报告](../../S08-完成报告.md)和[同一交接](../../../../../任务交接.md)。原r1失败及零调用准备记录均保留。

## 已结束：Q06引用校验无效，按约定停止

2026-10-23 16:03:11–16:04:17 +08:00，以上收费命令实际只执行一次，进程退出1，`status=stopped`、`stop_code=formal_judge_invalid_Q06`。本轮发送12次（被测6/J1正式6/新增校准0），全部HTTP200、finish_reason=stop，逐次一POST，重试0；前5例完成，Q06裁判无效，Q07–Q16未发送。**本轮评价未完成，完整S08仍未通过；原Q07/Q10重复归因本次尚未验证到。**

Pro三例校准的原始响应与存档/冻结预期重新核对3/3；本轮6次Pro响应全部保持同一服务fingerprint，校准复用条件没有被本次引用无效自动抹去。冻结校准不覆盖所有正式引用表示边界，不能用3/3抵消正式invalid。

### Q06发生了什么

[Q06校验](validations/Q06-judge.json)唯一错误为`evidence_3_quote_not_contiguous_source_text`，对应C04。原J1 JSON结构有效、status自报scored，六项布尔/分值均在范围内；当前本地规则因连续原文引用不成立将其判invalid，未把原响应改成通过。

[定位证据](Q06-quote-diagnosis.json)显示：J1 quote与[候选Q06](candidates/Q06-response.json)的C04 reason解码文字**完全相同**；但候选在J1输入中是`candidate_feedback` JSON字符串，reason中的`out["known_minutes"]`双引号被JSON序列化为带反斜杠的文本。quote不是该序列化字符串或原学生代码中的连续片段，故未过冻结校验。这是候选字段原文与序列化引用表示的边界问题，**不等于J1凭空捏造理由，也不证明C04语义判断错误**。

本轮没有在看到结果后对quote反转义、修改判分器/校验器、转录原响应或补调用；保留invalid并停止，符合既定无效停止政策。下一步仅建议先离线明确引用单位与序列化契约，并形成可审阅差异/对照；尚未实施该新修复，任何新轮需明确范围，不能自动用掉未用20次。

### 用量、费用和剩余

| 项目 | 本轮实际 |
| --- | --- |
| 授权 / 实际调用 | 32 / 12（Flash6、Pro正式6、校准0） |
| 未用次数 | 被测10＋Pro正式10＝20；本轮已停止，不自动续用 |
| 真实usage | 输入29255、输出7792，共37047tokens；cache hit13312 / miss15943 |
| 已知usage按峰价全输入未命中上界 | **0.30904500CNY**：Flash0.05748600、Pro0.25155900 |
| 账本已用/保留预留上界 | **0.40580400CNY**；其中Q06无效裁判保留整笔预留0.137538，而其已知usage上界为0.040779 |
| 2元硬限未用差额 | 1.59419600CNY，按保留预留口径；不是账户余额或新轮许可 |

这两个费用口径均不是账户扣款。没有查账户或充值；失败调用计次且保留最大预留，不将已知较低usage上界退作自动续跑许可。加上旧S08 r1实际35次，S08两轮累计47次；已知usage同口径上界1.15193600CNY，已用/保留预留累计1.24869500CNY，旧轮及新轮上限分别约束，不互借。

### 原始结果与本地核对

[result-audit](result-audit.json)104项核对通过：12组原POST/HTTP响应/Provider结果、usage/角色/参数/预留与候选绑定一致。原计分脚本作确定性版本适配后重放，生成[rule-summary](rule-summary.json)：`status=not_completed`、`quality_metrics=null`，明确列Q06 invalid及Q07–Q16 not_run；没有用5例成绩替代16例分母。

原始输入、6候选、6裁判、6校验和12组raw均保留，见本目录相应文件夹及[执行输出](execution.stdout.txt)。本轮未改产品源码、数据库/旧分析/阈值或提示，未重跑旧工程、浏览器、Spark或规模实验，无常驻服务需清理；不自动提交、推送、部署或开始S09。最终文件检查见[final-qa](final-qa.json)。恢复先读账本与Q06定位，**禁止重发本轮--execute**。

最终文件检查实际通过：6个Python AST、80个JSON、174个本地链接，常见凭证模式无命中，`git diff --check`退出0，冻结案例/评分表Git状态无差异。该检查没有新增模型或数据库调用，不把文件检查通过当作真实质量通过。
