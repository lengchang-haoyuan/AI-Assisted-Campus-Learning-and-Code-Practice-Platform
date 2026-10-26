# S08新提示完整固定评价：运行r4

被测提示`practice-review-r3`、Schema`practice-review/1.0`；J1 `judge-r4`，计分沿用`evaluation-method-r3`，仅新增candidate-v3/text3.0身份适配。冻结16例、答案、9/69/18分母与阈值均不变，旧结果不混入本轮成绩。

用户已对完整范围明确答“授权上述32次及费用上限（推荐）”，见[授权记录](authorization.json)：DeepSeek `deepseek-flash`被测最多16次、`deepseek-v4-pro`J1正式最多16次，共32次，新校准0。输入限固定16例代码/声明/指定向量及原合成白名单Context，J1另见单例冻结参考；隐藏被测身份元数据。

货币硬限1.562968CNY，原r2及续办已用/保留0.437032CNY不释放，合计不超过原2CNY。每POST前按完整消息UTF8字节+512、峰价输入全cache-miss和最大输出预留；成功按真实usage同口径上界结算，失败占次并保留预留。账户余额/扣费未查询，不充值。原未用角色已并入本轮32次，不重复叠加。

参数见[parameters.json](parameters.json)，温度0、json_object、thinking disabled、输出上限1500/1200、总超时60秒、应用/transport重试0。Pro原校准3/3材料/提示/参数本地重验通过，每个新Pro响应须匹配原服务指纹；Flash也须匹配原服务版本。变化/Provider失败/无效/弃权/预算不足即停止；普通质量失误按固定集收齐后如实汇总。不自动加次、调参、换例或降低阈值。

[本地检查](local-checks.json)：16项评分回归、20项调用守卫、7份Python AST、16请求预检及Pro校准3/3通过，均零真实凭证/网络/数据库/学生代码执行。[preflight.json](preflight.json)保留预检结果。

根目录仅执行一次：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261024-flash-pro-r4/run_evaluation.py --execute
```

已有账本或raw目录会拒绝重跑，中断后先只读账本。所有写入限定在本目录，不写数据库、不执行学生代码、不改S06批次、不推进S09，不提交/推送/部署。实际执行结果和账本在本轮结束后追加到下方及原S08报告。


## 实际执行：首例结构无效，已停止

2026-10-24根目录按上文命令仅执行一次，exit1、`AgentOutputValidationError`。新Flash1/16、Pro0/16、校准0、重试0；Q01响应HTTP200/stop，model和服务指纹均与预期一致。六个criterion都含七个键，但C06的verdict为null，只允许pass/fail/unknown，因此原校验拒绝，未送J1，后15例未运行。

[诊断](Q01-output-diagnosis.json)、[原请求](raw/01-under_test-Q01-request.json)、[原响应](raw/01-under_test-Q01-response.json)、[无效草稿](invalid-candidates/Q01-response.json)、[逐例状态](case-status.json)保留实际值，不把null补成pass/unknown，也不混入旧6例。原始usage2252输入/576输出=2828tokens，已知usage峰价全输入miss上界0.009112CNY，失败保留整额预留0.032356CNY；[账本](ledger.json)、[累计预算](cumulative-budget.json)与[12项实际审计](result-audit.json)已保存。无Provider-result文件，因为Agent结果解析前已失败，不伪造成功文件。

与此前原r2及续办合计已用/保留0.469388CNY，原2元差额1.530612CNY；本授权余Flash15/Pro16共31次，失败轮已结束，不自动续用。S08历史累计49次/139268tokens，已知usage上界1.169202CNY、含预留1.312279CNY；未核对真实账户扣费/余额。

**提示r3未通过真实结构有效性，完整S08仍未通过。** 当前请求只有json_object语法模式，Schema写在system文本，非供应商Schema生成约束。建议下一步只做[结构化输出适配方案](结构化输出适配方案.md)中的现有Provider可选Responses JSON Schema离线适配（模型0），待明确范围后实施，不继续收费试词。方案待确认，尚未改Provider/BaseAgent；本轮停止，不进入S09。
