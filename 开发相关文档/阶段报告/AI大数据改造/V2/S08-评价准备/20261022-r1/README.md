# S08 固定案例评价准备（20261022-r1）

当前只完成离线准备，**被测模型、J1新校准、J1正式评分均未运行，授权调用与实际费用均为0**。本目录没有被测/裁判原始模型结果。`candidate_feedback: null`是待填输入模板，不是模型弃权结果。S08质量门槛仍待评价，不以工程或本地检查代替模型质量。

## 冻结依据和输入边界

- [S01-r2案例与原始规则](../../S01-AI固定模板与评价案例.json)、[评分表](../../S01-评价评分表.md)及[确认记录](../../S01-确认记录.md)保持原样。
- [16例索引](case-index.json)仅供评价人员和规则程序使用，包含冻结标签，不能整包发送给被测模型。
- `under-test/`中每例只含固定任务、criterion定义、本例代码/声明、以及**case.test_ids指定的原始公开向量**。例如Q02只选T02，Q03选T03/T05/T07。没有参考代码、标签、参考issue、其他案例或评分阈值。
- [全部7个向量的参考备份](fixed-vectors-reference.json)供离线核对；不替代逐例选择。生产提交的本人输出核对仍是T01/T04，不把它与16例评价输入混用。
- `judge-input-templates/`中的J1每次只见本例固定标签/行为、代码、criterion和0–3分规则。真实被测响应到位后，按原文固定版本填入`candidate_feedback`，隐藏被测厂商与型号。不得把J1参考回填到被测输入。
- 只静态读代码，不运行学生代码；不连接数据库、不读取应用配置或凭证。

## 单例入口

| case | 冻结类别（仅评价侧） | 指定向量 | 被测输入 | J1待填模板 |
| --- | --- | --- | --- | --- |
| Q01 | 正确 | T01 | [输入](under-test/Q01-input.json) | [模板](judge-input-templates/Q01-input.json) |
| Q02 | 正确 | T02 | [输入](under-test/Q02-input.json) | [模板](judge-input-templates/Q02-input.json) |
| Q03 | 正确 | T03/T05/T07 | [输入](under-test/Q03-input.json) | [模板](judge-input-templates/Q03-input.json) |
| Q04 | 正确 | T04/T06 | [输入](under-test/Q04-input.json) | [模板](judge-input-templates/Q04-input.json) |
| Q05 | C01问题 | T06 | [输入](under-test/Q05-input.json) | [模板](judge-input-templates/Q05-input.json) |
| Q06 | C03问题 | T01 | [输入](under-test/Q06-input.json) | [模板](judge-input-templates/Q06-input.json) |
| Q07 | C03问题 | T01/T02 | [输入](under-test/Q07-input.json) | [模板](judge-input-templates/Q07-input.json) |
| Q08 | C02问题 | T04 | [输入](under-test/Q08-input.json) | [模板](judge-input-templates/Q08-input.json) |
| Q09 | C04问题 | T01 | [输入](under-test/Q09-input.json) | [模板](judge-input-templates/Q09-input.json) |
| Q10 | C03问题 | T05 | [输入](under-test/Q10-input.json) | [模板](judge-input-templates/Q10-input.json) |
| Q11 | C05问题 | T03/T07 | [输入](under-test/Q11-input.json) | [模板](judge-input-templates/Q11-input.json) |
| Q12 | C02问题 | T02 | [输入](under-test/Q12-input.json) | [模板](judge-input-templates/Q12-input.json) |
| Q13 | C06问题 | T01 | [输入](under-test/Q13-input.json) | [模板](judge-input-templates/Q13-input.json) |
| Q14 | 信息不足 | T01 | [输入](under-test/Q14-input.json) | [模板](judge-input-templates/Q14-input.json) |
| Q15 | 信息不足 | T01 | [输入](under-test/Q15-input.json) | [模板](judge-input-templates/Q15-input.json) |
| Q16 | 信息不足 | T01 | [输入](under-test/Q16-input.json) | [模板](judge-input-templates/Q16-input.json) |

各例的固定candidate artifact_id、文本版本、未运行状态和后续原始文件槽位见[可执行清单](evaluation-checklist.json)。`agent-input-templates/`另提供可通过生产Input DTO的离线调用材料：UUID由固定artifact_id确定，context_version=1、attempt_no=1只作合成评价身份；它们不是数据库里的产品attempt，不声称存在会话或发生过提交。原始被测数据与生产Agent DTO分开保存。

## 校准与模型条件

[judge-r4原文](judge-r4-system.txt)、[G01](calibration-inputs/G01-input.json)、[G02](calibration-inputs/G02-input.json)、[G03](calibration-inputs/G03-input.json)均从S06已保存材料逐字复制；[冻结预期](calibration-expected.json)仍来自S01-r2。旧失败记录和固定答案未覆盖。

[配置提案](judge-config-proposal.json)保留S06历史provider=`deepseek`、请求model_id=`deepseek-flash`、当时服务版本`DeepSeek-V4.1-Flash-1017`、temperature=0、max_tokens=1200、JSON模式、关闭思考、超时及重试0。**这些是历史配置，不是本轮已选择或获授权的型号。** 被测角色已对齐[生产契约绑定](production-contract-binding.json)：`practice-review/1.0`、`practice-review-r1`，保存了[模型输出schema](review-draft-schema.json)、[Agent输入schema](review-input-schema.json)及[角色提示词原文](review-role-instruction.txt)；真实调用前仍需复核源码与实际Provider参数。

只有新选J1的provider、精确实际服务版本、judge-r4原文、全部调用/采样参数与固定校准材料保持一致，且确认别名未切换服务版本，才能复用S06校准。当前复用状态为`not_verified`。变更任一条件需要新批次G01–G03校准3/3，不修改预期；失败即停止正式评分。默认被测与J1使用不同精确model_id；同型号只能标“同模型辅助诊断”。

## 固定计分和预算

[规则汇总](rule-summary.json)逐项保留原定义与门槛：13个完整案例共78个已知单元=9个问题+69个正确单元，另18个未知单元。TP须正确标fail且J1确认对应证据；FP照69个冻结正确单元算。全部9个错误例都进入可执行性分母，漏报固定0，裁判abstain/invalid不剔除。

完整质量门槛同时满足：TP≥8、FN≤1、精确率≥0.80、FP≤3且FP/69≤0.05、错误通过0/9、3/3信息不足且无无依据确定判断、正确确认≥3/4、可执行性≥8/9得分至少2且9例总分≥18，无无效结构或未解决裁判项，并有有效校准依据。未运行不能填0或通过。

[预算方案](budget-plan.json)仅是待授权清单：被测16次×最多1500输出tokens，J1正式16次×最多1200输出tokens；若不能复用校准另3次×最多1200。共32次正式或35次含新校准，角色额度不互借，Provider失败也计数，client/transport重试均0。S06历史7/7已用完，剩余0，不借入S08。输入token与费用尚未核算，方案不构成任何调用许可。

[角色账本](role-ledger.json)记录本轮各角色授权0、实际0、tokens0、费用0及未运行原因。没有读取账户扣款或凭证。

## 本轮已执行的离线检查

在项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -B "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价准备/20261022-r1/validate_inputs.py"
```

输入、冻结分母、逐例指定向量、参考隔离、历史提示词/参数、候选未运行、生产DTO/schema/prompt及零调用账本共199/199项通过，见[准备核对记录](preparation-check.json)。这是文件和输入契约正确性检查。

[新J1响应校验器](../../S08-历史评价工具归档.zip)支持Q01–Q16的六个criterion及G01–G03校准，校验case绑定、状态、类型/范围、逐项完整性和连续原文引用。旧S06校验器只允许G01–G03/C01，不能直接用于正式16例。用S06三份历史真实响应回放本地新校验器3/3通过，见[历史响应回放](historical-calibration-validator-check.json)；它只证明校验器能处理旧证据，不是本轮新校准或已确认复用。

[确定性汇总脚本](../../S08-历史评价工具归档.zip)只读取已有真实文件；不带参数运行会输出`not_run`和`quality_metrics: null`。任一案例缺失、结构无效、J1弃权或无效时保留未完成，不生成伪零分，也不丢弃分母。候选结构使用生产`PracticeReviewDraft`验证并核对代码引用，正式J1响应再经六criterion校验。它只计算冻结规则，不替调用账本、当前校准和独立型号核对做最终阶段验收。

未来真实材料齐全时，可运行：

```powershell
.\backend\.venv\Scripts\python.exe -B "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价准备/20261022-r1/score_results.py" --candidate-dir "真实被测响应目录" --judge-dir "真实裁判响应目录"
```

被测每例`Qxx-response.json`包裹`case_id`、`artifact_id=S08-Qxx-candidate-v1`、`text_version=1.0`和原始模型JSON`response`；保留厂商原始响应另存，不用这个包裹代替usage/耗时/费用。裁判每例同时保存真实`Qxx-input.json`及`Qxx-response.json`；输入须逐项等于本目录模板，只将`candidate_feedback`填为原始被测JSON的`json.dumps(..., ensure_ascii=False, indent=2)`固定文本。裁判响应包裹`case_id`、`candidate_artifact_id`、`candidate_text_version`及`response`，程序核对绑定。不要用校验器生成或补写候选答案。

## 恢复顺序与停止点

1. 先读S08完成报告、任务交接与本目录账本，保持本轮模型调用0。
2. 复核review输入/输出schema、提示词版本与本目录快照未变，再选择实际Provider参数和白名单评价Context；不向模型发送参考索引。
3. 另行明确被测/J1两个角色精确provider/model_id、允许发送的输入、各角色次数与合计货币上限；不能把本目录方案当许可。
4. 逐条件核对历史校准可否复用；需新校准则先G01–G03，3/3才进入正式评分。保留每次原始请求/响应、参数、耗时、tokens、费用和失败，不自动重试或调参。
5. 每例独立被测后固定candidate文本，再把该例参考和candidate交J1。全部16例逐项规则汇总；任何缺失/无效/弃权如实保留，不改标签或阈值追求通过。

准备完成即停止；不启动真实评价，不替root执行阶段交接或下一阶段。
