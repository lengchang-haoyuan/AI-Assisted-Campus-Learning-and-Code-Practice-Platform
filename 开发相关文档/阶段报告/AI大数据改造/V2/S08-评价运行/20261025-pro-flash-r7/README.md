# S08已知引用错误修复与重评r7

**当前：已知引用修复及本地检查完成；真实r7按失败即停结束，完整S08质量仍未完成。** 用户授权补5次/完整32次后，实际Pro6/Flash5共11次，Q01–Q05评分完成；Q06含C04 unknown却给overall=needs_changes，被原一致性校验拒绝，Q07–Q16未运行。该响应还存在夸大计数错误影响的无依据陈述，不能只改汇总追认通过。 用户要求“修改所有错误后再次尝试”。本轮仅S08生成侧引用约束与新运行版本，不扩展平台、不删教师、不改DB/API/依赖或冻结答案阈值，原dirty工作及r1–r6成功/失败原件保护。

## 修复和没有冒充的成绩

提示practice-review-r6、请求practice-review-responses-schema-r3，Pro deepseek-v4-pro仍Responses JSON Schema/1500，Flash deepseek-flash仍Chat judge-r4/1200；温度0/非思考/超时60/重试0。新生成侧pass和unknown的evidence_span强制null；fail仍按模板对应issue_type，只生成<=300字符短单行连续原文，不添加省略/行号/Markdown，不拼接代码。原代码确含...或…可原样引用，不能全局删除这些字符。理由/动作仍按字段保留。

公共practice-review/1.0、原build_result逐字引用校验和各项完成门槛不动；历史pass/unknown合法连续引用仍可读，旧Q03拼接引用仍拒绝，未去省略号/补值或重标旧输出。只有新请求收紧生成约束，旧固定参考和阈值不变。[修复矩阵](repair-matrix.json)区分历史工具问题、生成字段/类别/引用与真实语义质量，不能保证模型以后永不出错。

## 本地证据

[40项相关后端测试](backend-tests.txt)：cwd backend，`.venv/Scripts/python.exe -B -X utf8 -m unittest tests.test_practice_review tests.test_practice_structured_output tests.test_practice_agent -v`，exit0。覆盖新null/单行/300约束、原Q03仍拒绝、原Ellipsis与中文反斜杠不篡改、历史非fail合法引用兼容，以及字段/类别/unknown/缺代码和旧Chat兼容。

[24工具测试](local-unittest.txt)、[20调用守卫](runner-guard-check.json)、[16请求预检](preflight.json)通过，模型调用/DB/凭证读取0。旧UTF8入口未改，r6的78项（含9编码）证据引用，不重跑前端/MySQL/Spark/规模实验。Mock完整32次是临时控制夹具，已清理，不是实际AI质量。

[生成Schema](wire-output-schema.json)、[公共Schema](review-draft-schema.json)、[完整Q03请求未发送](Q03-prepared-request-not-sent.json)、[参数](parameters.json)已固定。评分算法仍evaluation-method-r3，仅新增candidate-v6/text6.0版本绑定；引用validator和冻结输出模型与r6逐字相同。

## 校准、次数和金额

[Flash校准复用](calibration-reuse.json)仍S06 judge-r4三份实际wire一致、3/3有效，正式逐次核原e72d指纹；变更即停，不新增校准。J1提示/量表不改，旧Pro校准不借用。

新提示需完整Pro16＋Flash16共32次，旧r6两例不混入新成绩。旧余Pro13/Flash14=27次，因此需要明确补Pro3/Flash2共5次；[待确认授权](authorization.json)。费用仅使用已批准预算未用1.578880CNY，旧r2链已用/留1.193212合上限2.772092，不再提高货币总限。[预算](budget-plan.json)包含完整payload+512保守准入，预算/余额不足即停；不是余额或扣款保证，也不保证最坏整轮完成。

当前没有真实ledger/raw。明确新范围后只一次run_evaluation.py --execute；任何中断先--ledger只读恢复，禁止重复收费/自动重试/调阈值或另起新轮。失败也自动保存原始响应、无效候选、逐例状态和部分规则汇总；审计只读audit_results.py。最终无论通过与否更新原S08报告/日志/同一交接，不推进S09或提交/推送/部署。


## 真实r7执行与结论

用户对call_b397d7cc52be4473be7aa91fc00d9323/0明确“授权补5次，运行完整32次（推荐）”，[实际授权](authorization.json)及[执行前检查](execution-preflight.json)保留。一次--execute，exit1/AgentOutputValidationError，[stdout](execution.stdout.txt)，stderr空。实际Pro6 Responses均HTTP200/completed、Flash5 Chat/stop且原校准指纹一致；新校准0、重试0。

Q01–Q05完成有效评审/辅助评分，旧Q03拼接引用未重现。Q06 C03/counting分类正确、引用`out["record_count"] += 2`精确存在，但C04标unknown、overall标needs_changes；按原规则任何unknown应insufficient，故被原Public validator拒绝，Flash未评分Q06。[具体诊断](Q06-output-diagnosis.json)、[原无效响应](invalid-candidates/Q06-response.json)保留，不更改overall或裁判分数。

还应区分格式与语义：Q06仅record_count错误加2，其余known/missing计数和分钟累加代码不随该变量重复执行。模型却把它说成行集合扩大、多个字段翻倍，并据此把C04说成材料不足；冻结参考C04为pass。这是尚未通过的AI理解/依据质量，修正汇总字段不能自动解决，不能宣称“所有模型错误已消除”。

[逐例状态](case-status.json)5scored/1无效/10未运行，[部分规则汇总](rule-summary.json)质量指标null、分母9/69/18保留。[112项实际结果审计](result-audit.json)通过，证明原请求/原文/角色/终态/校准/用量可核，不是模型质量通过。

本轮48734输入/7461输出=56195tokens；已知usage峰价全miss费用上界0.494409CNY、保守已用/留0.657309，含Q06全留0.239796。旧r2链合已留1.850521/上限2.772092，本轮余0.921571；剩Pro10/Flash11共21次不自动续用。S08累计76次/265486tokens，usage上界2.201798/含预留2.693412CNY，S06另7次；未查真实账户扣款、余额或充值。[累计账本](cumulative-budget.json)、[实际账本](ledger.json)保留。

当前轮到此停止，无额外修提示/重试/新轮收费，不推进S09/提交/推送/部署。无DB写入或清理，学生代码未执行；Mock临时夹具已清理，旧证据/未提交工作保留。恢复先只读r7诊断/账本，下一步若继续须处理汇总一致性及计数变量/行集合语义边界，并另明确新真实范围。
