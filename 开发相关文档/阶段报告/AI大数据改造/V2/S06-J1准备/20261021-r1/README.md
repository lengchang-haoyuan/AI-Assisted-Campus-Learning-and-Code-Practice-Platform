# S06 J1 收口准备 r1

日期：2026-10-21，Asia/Shanghai。依据 V2-S01-r2 与本轮“只执行 S06 收口、无新增模型许可时准备并保持待评”指令。

**准备完成；工程 / 数据 / 实验沿用既有成果，J1 未校准、正式专题未评分，完整 S06 未通过，S07 原前置未满足。实际授权 0 次、消耗 0 次、费用 0、剩余授权 0。**

## 审阅入口

| 文件 | 内容与使用边界 |
| --- | --- |
| [解释稿-v1.md](解释稿-v1.md) | 独立待评文本，artifact_id=`S06-analysis-b96ea63e-v1`，文本版本 `1.0`；只解释既有同批事实 |
| [source-numbers.json](source-numbers.json) | 主 / 边界身份、冻结数字、39个原文件及JSON pointer引用；保留各自cutoff，不混合两主体 |
| [judge-r2-system.txt](judge-r2-system.txt) | 从已批准评分表原样提取的系统提示词 |
| [G01](G01-input.json) / [G02](G02-input.json) / [G03](G03-input.json) | 三份独立反馈校准输入；仅使用固定设计Q05代码与冻结反馈，不执行代码 |
| [calibration-expected.json](calibration-expected.json) | 冻结校准预期，单独保存，**不放入模型输入** |
| [analysis-input.json](analysis-input.json) | 正式专题输入：artifact、同批事实、问题、四图数字路径、四维rubric及完整解释正文 |
| [response-contract.json](response-contract.json) | 两类输出结构、分值范围与必须由外部规则执行的语义检查；本轮没有模型输出可供验证 |
| [budget-ledger.json](budget-ledger.json) | 当前授权 / 实耗、待授权配置、3+1方案、跨阶段36方案与以后每次尝试的记账字段 |
| [not-run.json](not-run.json) | 零调用原因，校准与正式得分均未运行，空白保留null，未伪造原始响应 |
| [verify_preparation.py](verify_preparation.py) / [verification.json](verification.json) | 只读本地检查与实际输出；不是J1评分，也不测试模型的语义判断能力 |
| [git-baseline.txt](git-baseline.txt) | 本轮开始的Git状态；已有S06、DOCX、设计和本机状态均需保护 |

## 固定身份与数字

主发布batch=`b96ea63e-419e-4293-b724-d1ce59bd85ba`，owner3，snapshot=`s06-e2e-owner3-20261021`，job=`s06-e2e-main`，ODS输入batch=`26976f4e-29f3-4393-bc46-814ab5db36ae`。主cutoff=`2026-10-21T05:22:27.611955Z`。主事实为90分钟、5记录、缺失2，任务2/4，群组3、修订1、确认2、待评1，反馈覆盖2/3。不是S01 D00的75分钟设计样例。

边界发布batch=`3217db64-1302-4722-a483-c3b1ad7b980f`，owner4，snapshot=`s06-e2e-owner4-20261021`，job=`s06-e2e-boundary`，ODS输入batch=`a31b90f3-80e3-4931-a350-f7be1f670bff`。边界cutoff=`2026-10-21T05:22:27.640605Z`。使用r2独立答案199/200、逾期1；原截止的逾期0及失败记录保留。共同窗口10月19–20日，Asia/Shanghai，但两份快照是独立一致性事务。

原始清理证据显示临时ID8已删而90分钟历史保留；本轮没有连接源库核实当前行数，不重建ID8或用75分钟改写旧批。首次反馈极短来自自动API验证；虚构受控数据、记录覆盖和教师确认不能推出自然教学速度、因果关系、个人能力或服务器执行代码。

## 本轮实际检查

从项目根执行：

```powershell
& .\backend\.venv\Scripts\python.exe -B -X utf8 '开发相关文档/阶段报告/AI大数据改造/V2/S06-J1准备/20261021-r1/verify_preparation.py'
git diff --check
```

脚本只读本地固定JSON/JSONL和本目录，不导入应用、不读取环境凭证、不创建AIClient，不连接数据库、服务或WSL。校验：身份与输入/发布batch区分、同批独立答案→ADS→载荷→已保存发布详情、日字段映射、冻结比例、边界cutoff与旧预期、解释引用与文本、judge-r2原文、G01–G03材料及预期、四维/分值结构、普通令牌模式及当前零授权。`verification.json`给出本轮实际检查数和各消息字符数，字符数不是tokens计费数。

现有Provider消息限制为每条12000字符、总24000字符。未来经授权时，system使用`judge-r2-system.txt`，user使用对应input JSON经`json.dumps(..., ensure_ascii=False, separators=(',', ':'))`序列化的完整对象；每次只发送一例，全新上下文。不要把本README、账本或校准expected混入输入。当前四份user输入均在限制内；本轮仅检查结构，没有调用Provider。

历史30项相关后端、前端类型/构建、真实浏览器和两档实验只引用[原S06报告](../../S06-完成报告.md)，本轮未重跑。没有改业务源码、API、数据库、依赖、运行配置或旧完成产物。

## 精确预算与未运行原因

| 角色 | 本轮待授权方案 | 每次输出上限 | 当前授权 | 实际尝试 |
| --- | ---: | ---: | ---: | ---: |
| J1校准G01–G03 | 3 | 1200tokens | 0 | 0 |
| J1正式analysis | 1 | 1200tokens | 0 | 0 |
| 本阶段合计 | 4 | 合计最多4800输出tokens | 0 | 0 |

provider、精确model_id、允许发送输入、币种、价格与合计货币上限均未获得新许可，账本相应项为null；实际费用及已授权可用金额为0。不能从全站默认配置、已有凭证或36次计划推导授权。输入tokens和实际计费依选定模型 / Provider，当前未测量；4800是输出token计划上限，不是费用上限。

待授权参数方案：`judge-r2`、temperature=0、max_tokens=1200、response_format=`json_object`、reasoning_enabled=null（尚未选择Provider，生效语义需核对）、total_timeout_seconds=60、max_retries=0、retry_base_delay_seconds=0、max_retry_delay_seconds=0；逐例新上下文。未激活这些配置。模型不支持时停止并明确差异，不能静默替换或调参。未来评价只复用现有Provider / AIClient，显式设置`max_retries=0`，不改全站策略。**本目录没有在线执行器，运行本地检查不会发起模型请求。**

跨阶段36次方案仍是S08被测16 + 首次共享校准3 + S08正式裁判16 + S06专题1。当前校准未运行，不能复用；若未来3/3通过且精确provider/model、judge-r2、参数和校准材料未变，可供S08复用，校准仅在总方案中算一次。计划未执行的次数不是已授权剩余额度；当前剩余授权仍为0，角色不得互借。

## 下一次恢复与停止点

1. 先读[持续交接](../../../../../任务交接.md)与最新用户指令，核实是否新增精确模型、输入、3+1次数及货币授权；没有则继续待评，不询问重复的A/B设计批准。
2. 实际调用必须在新的评价运行目录保存精确配置、授权与价格依据、每次原始输入/响应/失败、耗时、tokens和费用；不覆盖本准备版本或既有成功/失败证据。Provider尝试一开始就消耗本角色次数，失败同样计数，不自动重试。
3. 依次校准：G01=scored/3/C01有效/无无依据声明；G02=scored/0/C01无效/有无依据声明；G03=abstain/null/C01未知/声明未知。全部逐项命中才可正式评分；任何校准不匹配或异常停止正式评分，保留实际消耗。G03的预期弃权属于校准通过条件，不表示正式分析可弃权通过。
4. 正式analysis只评当前artifact，四项0–2、逐项引用定位、分数由外部规则相加，≥6/8且夸大=false；实际abstain、invalid、引用缺失、数值冲突或不足6分均保持未完成。先定位材料，不倒改冻结答案、阈值或旧产物追求通过。新一轮调用另获明确范围。
5. 本轮在准备完成即停止；完整S06尚未通过，S07原前置未满足。用户另行明确调整前置时仍须原样交接J1缺口，不能改写成绩。

恢复仅涉及本目录和本轮对报告、证据索引、累计日志及同一任务交接的增量；不回退整个工作区，不清理历史 / tmp / .rivet，不自动提交、推送、发布、部署或推进下一阶段。
