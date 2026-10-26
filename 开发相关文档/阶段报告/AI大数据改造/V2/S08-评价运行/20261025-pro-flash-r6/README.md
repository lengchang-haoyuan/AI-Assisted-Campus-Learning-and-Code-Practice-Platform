# S08 Pro评审与Flash辅助评分：工具和UTF-8优化r6

**当前：离线优化通过，真实r6已按失败即停结束；完整S08质量未完成。** 用户明确授权Pro16/Flash16、本轮2CNY后，实际Pro3/Flash2共5次；Q01–Q02完成评分，Q03在pass代码引用中插入省略号/拼接不连续原文，被原逐字引用校验拒绝，Q04–Q16未运行。新角色/Schema/UTF8网络响应已真实接受，未自动修补或重试。 用户已明确优化工具、项目输出UTF-8、Pro评审与Flash评分。原S08工程/数据成果及r1–r5所有原始失败保留，不写库、不推进S09、不删除教师模块。

## 角色、材料与固定规则

[精确参数](parameters.json)：被测deepseek/deepseek-v4-pro，Responses JSON Schema、max_output_tokens1500；辅助评分deepseek/deepseek-flash，Chat JSON_OBJECT、judge-r4/max_tokens1200。两者temperature0、非思考、connect5/total60秒、客户端/transport重试0、不自动降级。角色只在本轮评价实例中互换，全站默认模型不改。

新的生成侧Schema为pass/unknown通用分支加6个criterion专属fail分支，共8分支；fail issue_type直接复用现有模板映射，堵住C05/counting等组合。提示practice-review-r5、请求practice-review-responses-schema-r2，公共Schema仍practice-review/1.0，服务器原校验不放宽；不重新归类/补值旧模型输出。新候选candidate-v5/text5.0。固定Q01–Q16代码、声明、选定向量和合成白名单Context不变，被测不见参考标签/代码/阈值，Flash只见单例冻结参考和候选、不见被测型号身份。

[评分算法](../../S08-历史评价工具归档.zip)仍evaluation-method-r3，只有新提示版本绑定，阈值及9问题/69正确/18未知分母不改；引用验证器与r5逐字相同。Pro/Flash角色与提示已改变，旧5例不并入新成绩；只补尚缺的AI质量，需要完整新16被测+16正式辅助评分，共32次。工程、MySQL、前端、Spark与规模实验仍引用原证据，不重跑。

## Flash校准条件复用

[校准复核](calibration-reuse.json)逐个比较S06 20261021-deepseek-flash-r3-judge-r4的G01–G03：输入及完整Chat wire与当前完全相等，旧三份原raw响应按当前引用/预期校验3/3。原Flash指纹e72d3c7f663d3e1383b00b3884cb4501，正式每次继续核对；变化则标当前复用失效并停止，不自动新增校准。旧Pro校准不用于Flash。新增校准0，历史S06调用/费用不重复计入本轮。

## 工具实际优化

- 角色与型号从当前参数绑定到候选/J1 envelope，并由审计核原请求、raw、Provider与envelope一致，防止沿用旧Flash/Pro身份。
- 原始HTTP严格UTF-8，兼容BOM；坏UTF8、非JSON、空响应、非对象JSON均保留可逆base64原字节的UTF8 JSON包装并停止。先做凭证字节脱敏，绝不保存请求认证头；不使用errors=replace抹去原始问题。
- 响应状态按真实协议记录：Pro Responses为completed/input_tokens，Flash Chat为stop/prompt_tokens；已知失败usage照记，未知保持unknown，全预留不释放。
- 失败/中断也自动输出case-status和部分rule-summary，无效候选单列，不缩分母。评分JSON失败、服务指纹变化和原始异常均可审计，不能通过丢弃案例凑分。
- POST前完整payload含Schema的UTF8字节+512保守预算，成功按实际usage峰价全miss上界结算；失败算次数、留全预留，角色额度不互借，已有独占ledger/raw禁止重发。

## 项目UTF-8输出

新[Python编码入口](../../../../../../backend/app/core/encoding.py)在app/scripts包启动时原地设置stdout/stderr UTF8+strict，并设置Python子进程环境；无reconfigure的捕获流不替换或关闭。analytics入口只用stdlib独立做同样配置。S07/S08恢复和规模实验Python子进程显式-X utf8，单处分析JSON读取补UTF8。

项目根目录先执行`. ./scripts/Use-Utf8.ps1`，只影响当前PowerShell会话：控制台/管道/Out-File/Set-Content/Add-Content默认UTF8；PS7无BOM，Windows PowerShell5带BOM。新JSON证据仍由Python显式UTF8无BOM写入，不用重定向覆盖JSON。没有修改系统区域、profile、.env、依赖或数据库字符集。API JSON、网页meta、ODS写入和现有utf8mb4已正确，保持原格式；[282份活跃源码UTF8检查](utf8-source-inventory.json)通过，无旧文件批量转码。二进制、原始模型响应和旧成功/失败快照不改。

## 本地检查与真实边界

[78项后端原输出](backend-tests.txt)：cwd backend，`.venv/Scripts/python.exe -B -X utf8 -m unittest tests.test_ai_provider tests.test_agents tests.test_practice_agent tests.test_practice_review tests.test_practice_structured_output tests.test_utf8_output -v`，exit0。含旧Chat兼容、组合字段拒绝、中文Emoji/引号/换行/反斜杠、UTF8/BOM/UTF16与坏字节、ANSI父环境下三入口/日志/嵌套子进程/捕获流、实际PowerShell7与Windows PowerShell5重定向和profile未修改验证。

[24项评价工具原输出](local-unittest.txt)：根目录`backend/.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s <本目录> -p test_*.py -v`，exit0。包含历史引用/评分/账本回放，Pro Responses成功与失败，坏UTF8/非JSON/空响应原字节保存，Mock完整32次角色/协议/费用与审计、伪造envelope型号拒绝、Flash裁判坏JSON/指纹变化后的部分结果及费用审计。所有Mock调用是临时夹具，不写真实账本、不算模型质量；临时目录自动清理。

[20项调用守卫](runner-guard-check.json)及[16请求预检](preflight.json)通过。[本地汇总](local-checks.json)、[完整Q06请求未发送](Q06-prepared-request-not-sent.json)、[生成侧Schema](wire-output-schema.json)、[公共Schema](review-draft-schema.json)可审阅。没有真实模型、数据库或学生代码执行；Fake/Mock/ASGI不代替真实模型质量。

## 预算与真实恢复

[预算方案](budget-plan.json)建议Pro16+Flash16、新校准0，共32次；新硬上限2CNY。旧r2链已用/留0.772092，合新预算上限2.772092，高于原链2CNY，必须明确新范围。也可选原剩余1.227908CNY并在准入不足时停止。此前S08各轮已用/留1.614983CNY，未查真实账户扣费或余额；不会充值。

16个Pro完整请求最大预留之和3.739464CNY，历史候选的Flash预留场景0.531094；二者是极保守准入上界，不是实际费用。每次成功后实际usage结算会释放多余预留，但新输出长度未知，2元也不承诺最坏情况下整轮必完；余额/预算不足、Provider/结构/裁判无效或服务指纹变化立即停，自动重试0。当前[授权记录](authorization.json)仍false，建议额度不是许可。官方[价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)及[Responses结构](https://api-docs.deepseek.com/api/create-response/)于2026-10-25再次只读核实。

明确新轮具体次数/金额后，只一次run_evaluation.py --execute；任何中断先--ledger只读恢复，不重发execute。原字段、阈值、校准提示不调，不把旧5例或无效响应改成通过；完整结果后只交接，不启动S09。


## 真实轮r6结果与恢复

2026-10-25用户对call_09c06c0e40ec41fc83447047b7ca3e05/0明确“授权32次，本轮上限2元（推荐）”，[实际授权](authorization.json)和[执行前检查](execution-preflight.json)已保存；前述budget-plan为准备时点提案，执行只按明确授权。[stdout](execution.stdout.txt)记录一次--execute，exit1/AgentOutputValidationError，stderr为空。

实际Pro3 Responses均HTTP200/completed，Flash2 Chat均stop且保持原e72d校准指纹。Q03六项全pass、七字段/枚举/组合有效，但C02/C03/C05 evidence_span包含原代码中不存在的`...`，拼接跨段原文；当前错误是来源引用失真，UTF8无坏字节、无替换、无截断。服务端拒绝正确，Q03没有交给Flash评分。见[具体诊断](Q03-output-diagnosis.json)与[无效原文](invalid-candidates/Q03-response.json)。不删除省略号追认通过，也不调整阈值。

[自动逐例状态](case-status.json)为2scored、1被测无效、13not_run，[部分规则汇总](rule-summary.json)质量指标null，原9/69/18分母不变。原工程通过/UTF8本地检查保留，不能代替完整质量；新工具和角色实际可调用，原Q06的组合缺口已补，但本轮没有继续到该例，不宣称其真实语义已验证。

[52项实际结果审计](result-audit.json)通过：原请求/响应/两种终态/角色型号/候选与辅助评分身份/Flash复用条件及失败用量可核。23350输入/4212输出=27562tokens；已知usage峰价全miss上界0.263107CNY，保守已用/留0.421120，Q03失败全留0.238842。旧r2链0.772092合本次已用/留1.193212，授权合上限2.772092；本轮余1.578880及Pro13/Flash14共27次不自动重启。S08累计65次/209291tokens，已知usage上界1.707389、含预留2.036103CNY，S06另7次；未查真实账户扣款或余额。

[累计账本](cumulative-budget.json)及[实际账本](ledger.json)保留。无需DB清理或回滚，Mock临时目录已清理；所有旧证据/未提交差异及本次失败原文不删。不重发--execute、不收费修词、不推进S09/提交/推送/部署。若用户后续要求修复，最小建议是pass项不生成可选引用、fail仅短连续原文并做本地检查，新轮次数/费用另明确；此建议尚未实施。
