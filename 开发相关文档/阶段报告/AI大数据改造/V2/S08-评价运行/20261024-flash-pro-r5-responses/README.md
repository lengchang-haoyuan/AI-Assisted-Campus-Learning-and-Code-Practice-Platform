# S08新Schema协议真实评价r5

**当前：真实轮已按失败即停结束，完整S08质量未完成。** 用户已明确回复“授权”，本轮实际Flash6/Pro5共11次；Q01–Q05完成新候选与正式评分，Q06被测响应无效后停止，Q07–Q16未运行。新Schema协议已获真实HTTP200/completed响应，字段/枚举不再是本次失败原因；实际阻塞为Q06把C03计数错误标成C05/counting，原服务端映射校验拒绝。无重试/降级、无DB写入、不推进S09。

被测deepseek/deepseek-flash最多16次，提示practice-review-r4、请求practice-review-responses-schema-r1，`/responses` JSON Schema、max_output_tokens1500、终态completed；J1 deepseek-v4-pro最多16次，judge-r4、原Chat JSON_OBJECT/max_tokens1200/stop。两角色温度0、非思考、60秒总超时、重试0、禁止自动Chat回退。新增校准0，原Pro3/3只有精确材料/参数/指纹不变才复用；Flash Responses缺失Chat指纹如实unknown，不伪造或借用旧值。

仅固定Q01–Q16代码/声明/指定向量及合成白名单Context；被测不见标签/答案，裁判只见单例冻结参考和候选，不见被测身份。每例新候选candidate-v4/text4.0，不混入旧6例。公共Schema1.0、evaluation-method-r3、冻结答案与阈值/9-69-18分母不变。

用户已明确授权新轮32次/1.530612CNY，与前r2及续办保留0.469388合计≤原2CNY，并补旧31范围所缺Flash1次；见authorization.json。完整payload UTF8字节+512计入Schema，逐次预留费用后才POST；正常有效返回按实际usage/峰价全miss上界结算，失败保留全预留、计次并停止；未知usage保持unknown。原始响应、用量与账户扣款分开。预算不足在POST前停止，不承诺最坏整轮一定足够。

本轮仅新增运行/审计材料，不改产品源码、API、数据库、依赖、全站配置，不运行学生代码/旧全工程/前端/MySQL/Spark/规模实验。已有工程成绩引用S08原报告，不能替代新模型质量。提供商/结构/裁判无效/弃权或指纹变化立即停；普通质量未达标保留16例完整结果，禁止自动调参、补例或另起新轮。任何结束状态都不进入S09。

本地证据：[20项工具测试](local-unittest.txt)、[20项调用守卫](runner-guard-check.json)、[16请求及预算预检](preflight.json)、[原Pro校准复核](calibration-reuse.json)、[精确参数](parameters.json)、[冻结绑定](production-contract-binding.json)、[本地汇总](local-checks.json)。使用backend/.venv Python -B -X utf8，根目录运行`-m unittest discover -s <本目录> -p test_*.py -v`及`<本目录>/check_runner_guards.py`；均零真实请求。测试中首次仅夹具导入和SecretStr构造错误已纠正，最终20项通过，没有改生产Provider。

执行入口run_evaluation.py默认仅预检；仅具体授权后一次`--execute`，独占账本/原始目录防重发。任何中断先只读`--ledger`，不得再次--execute；原材料及失败请求不删。只读审计用audit_results.py，重新规则汇总用score_results_r3.py。完整16例方可报告固定质量结论，未完成不缩分母。

官方依据：[价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[Responses结构](https://api-docs.deepseek.com/api/create-response/)，2026-10-24公开只读核实。实际是否接受Schema以新轮HTTP原件为准。

## 真实结果与定位

| 验收层 | 实际结果 |
| --- | --- |
| 原工程/MySQL四路径 | 原S08通过证据保留，本轮不重跑 |
| 新协议真实兼容 | 6次Flash Responses均HTTP200/completed，原请求/响应已保存；5次Pro Chat/stop、原校准指纹一致 |
| 原Pro校准 | 本地重校验原G01–G03为3/3，新校准0；5次正式响应满足指纹复用条件 |
| 固定16例质量 | 5例scored、1例被测invalid、10例not_run；质量指标保持null，不缩9/69/18分母 |
| 失败停止 | 第11次Q06被产品原校验拒绝，后续请求0、自动重试0、无自动改提示/补值/重标 |
| 独立离线结果审计 | 102项通过，不代表模型质量通过 |

Q06代码原句`out["record_count"] += 2`被模型发现，但模型把C03判pass、把问题放在C05并使用counting。冻结参考及产品模板均要求C03/counting，C05仅允许empty_result_contract。不是换个字段名就可把旧结果追认为通过。当前生成侧Schema收紧七键/verdict/fail非空，却没有把criterion_id与issue_type的组合约束编码进去；服务端原校验正常挡下。后续若修复，建议仅补组合约束及正确归类提示、本地回归；真实新轮需另明确范围，旧响应不改写。见[定位](Q06-output-diagnosis.json)及[无效候选原文](invalid-candidates/Q06-response.json)。

[账本](ledger.json)实际11次、35713输入/6748输出=42461tokens；含失败usage峰价全miss上界0.275080CNY，保守已用/预留0.302704CNY，未核对账户扣款。Q06失败保留0.041362CNY全额预留，原usage不丢弃。合此前r2及续办保留0.469388，本链已用/留0.772092，距原2CNY余1.227908；本轮余Flash10/Pro11=21次不自动续用。S08各轮累计60次/181729tokens、usage上界1.444282、含预留1.614983CNY；S06另7次不混算。

实际命令（仓库根目录）：`backend/.venv/Scripts/python.exe -B -X utf8 <本目录>/run_evaluation.py --execute`，仅执行一次，exit1/AgentOutputValidationError；[stdout](execution.stdout.txt)、stderr为空。[结果审计](result-audit.json)由`.../audit_results.py`一次离线审计生成，exit0/102项；[逐例状态](case-status.json)、[部分规则汇总](rule-summary.json)、[累计账本](cumulative-budget.json)、[执行前检查](execution-preflight.json)、[校准引用](calibration-reuse.json)均保留。不重新执行--execute或历史轮，不清理原始失败。

本轮只新增实际评价产物并更新原报告/日志/同一交接；生产代码、公共API/数据库/依赖/配置、旧S06批次和未提交工作保持。无需数据库清理或回滚；恢复先只读本目录账本/诊断，当前收费轮已结束，不静默使用余量。后续阶段只能接收“工程原通过、AI质量未完成”的实际缺口，未执行S09。

授权补充：同一具体问题的后到明确答复“授权上述32次及1.530612元上限（推荐）”已另存[补充授权记录](late-authorization-confirmation.json)。原执行依据为更早的直接“授权”，原authorization/ledger/raw不改；该补答不新增轮次、次数或费用，本次追加调用0，r5仍11次后停止。
