# S08 真实评价单轮：Flash被测 / Pro裁判

本目录记录用户确认的单轮范围：[授权](authorization.json)、[精确参数](parameters.json)、[官方价格依据](pricing-basis.json)。**所有角色合计硬上限3 CNY**，被测`deepseek-flash`最多16次，J1 `deepseek-v4-pro`校准最多3次、正式最多16次，总计最多35次。没有充值、账户查询或自动重试许可。编写与默认预检时真实调用为0；实际执行后的状态和消耗以`ledger.json`为准，不把本README的准备状态当实际结果。

## 冻结材料和执行顺序

复用[已核对的离线输入和评分器](../../S08-评价准备/20261022-r1/README.md)、生产`practice-review-r1`/`practice-review/1.0`和judge-r4原文，不修改S01标签、规则、阈值、代码或指定向量。不同精确model_id用于被测和J1，逐次全新上下文。被测使用完全合成的固定白名单Context，无数据库、项目私文或学生代码执行；Context快照仅在实际执行阶段保存为`fixed-context.json`。

1. 新Pro裁判先运行G01–G03，必须3/3匹配冻结状态、分数和布尔预期，不复用S06 Flash校准。G03预期abstain正常匹配，与正式评价遗留弃权分开。
2. 按Q01到Q16固定顺序，每例一次Flash静态评审，再一次Pro单例评分，不选例、不调参、不追加调用。Flash候选只取原始draft JSON，J1不接收被测厂商、型号、usage或外层身份元数据。
3. 正常质量失误仍收齐固定16例。校准失败、Provider/结构异常、正式J1 abstain/invalid或预算不足立即停止后续；原始失败不覆盖，不自动重试。
4. 全部材料到位后复用确定性汇总：9问题、69已知正确、18未知的分母不变；无依据criterion证据不能被J1顶层false掩盖。只有有效校准、16例完成且所有规则门槛通过，账本的`S08_fixed_case_quality_passed`才为true。

## 费用守卫

[官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)由root于本轮核对；CNY/百万tokens峰价如下。

| 模型 | 输入缓存命中 | 输入未命中 | 输出 |
| --- | ---: | ---: | ---: |
| deepseek-flash | 0.04 | 2 | 8 |
| deepseek-v4-pro | 0.30 | 9 | 27 |

预算始终按**峰价且全部输入未命中**计算，不依赖缓存或非高峰折扣。每次请求前，以完整messages紧凑JSON的UTF-8字节数加512协议余量作为输入token上界，输出分别预留1500/1200 tokens。下一请求须满足“现有保守消耗或预留＋本次最大预留≤3 CNY”，否则在POST前停止。参数、模型、角色和总次数均受固定守卫约束。

计次和最大费用预留先写入并同步账本，实际请求正文也先保存；随后才发POST。成功后按真实usage计算同口径保守费用上界，释放预留差额。Provider、结构或当前响应导致停止时保留整笔预留；已知原始usage及相应峰价上界另留记录。usage缺失、输入/输出超预留或finish_reason不是stop时停止。所有金额使用Decimal。

这份账本不是账户实际扣款。客户端、transport重试均0；Provider失败也占用角色额度，不借用其他角色或S06额度。没有读取账户余额或验证充值能力。

## root执行历史与只读恢复

默认命令只检查本地材料，不构造AISettings、不读key、不请求模型、不连接数据库：

```powershell
.\backend\.venv\Scripts\python.exe -B "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261022-flash-pro-r1/run_evaluation.py"
```

root已于2026-10-22审阅后执行以下命令一次。**当前35次已经全部用完，不得重发本命令；保留它仅用于追溯。**

```powershell
.\backend\.venv\Scripts\python.exe -B "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261022-flash-pro-r1/run_evaluation.py" --execute
```

只有`--execute`阶段才在进程内读取项目已有DeepSeek key用于认证。已有`ledger.json`或`raw/`会拒绝盲重跑，包含只落了0次账本的启动中断；不自动恢复收费请求。恢复先只读：

```powershell
.\backend\.venv\Scripts\python.exe -B "开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261022-flash-pro-r1/run_evaluation.py" --ledger
```

进程退出0只表示整轮采集完成，可能是`completed_quality_not_passed`；阶段质量以账本布尔及规则文件判断。停止后先核对已发送次数、原始响应、保守费用和剩余授权，不能直接再次`--execute`补齐。

实际证据分别保存于`inputs/`、`raw/`、`calibration/`、`candidates/`、`judges/`、`validations/`和`rule-summary.json`。`raw/`只保存POST原JSON正文和响应body，不存认证headers；若上游正文意外包含key，先脱敏并立即停止。日志不输出配置、key、响应正文或私人文本。

## 本轮准备验证

- [默认预检](preflight.json)：199项准备契约通过，真实凭证读取0、网络0、数据库0。16份Flash请求与3份Pro校准请求的最大预留合计0.787564 CNY，不是实际消耗；正式J1金额依赖真实candidate，逐次核算，不冒称已静态保证整轮费用。
- [离线守卫自检](guard-check.json)：14/14通过，核对操作前已计次/预留、请求记录不含认证头、失败不退次数/预留、超3元在请求前拒绝、角色额度不互借、已有证据阻止盲重跑。
- 两个Python脚本语法通过。自检只使用本轮目录内临时合成账本和本地hook，没有transport或Provider请求、没有真实凭证；临时目录已清理，未在正式HERE留下`ledger.json`或`raw/`。

上述是执行前runner和材料检查，不是Pro校准或真实模型质量结果；原始准备记录保留，实际完轮结果如下。

## 已结束：工程通过，真实质量未通过

2026-10-22 10:52:47–10:55:23 +08:00，根agent已执行一次并完成35/35请求：Flash被测16、Pro校准3、Pro正式16；所有HTTP200、finish_reason=stop，每次一POST，自动重试0。校准G01–G03全部匹配3/3，G03预期弃权不是正式遗留弃权。未复用S06 Flash校准。

[账本](ledger.json)为`completed_quality_not_passed`，`S08_fixed_case_quality_passed=false`。[原始汇总](rule-summary.json)的TP9/FN0/FP2、precision9/11、误报2/69、错误通过0/9、信息不足3/3且误过0/3、正确确认4/4、九错误例可执行性全3分，数值门槛均通过。但Q07/C04与Q10/C04各有一项`evidence_valid=false`，合计`unsupported_issue_cells=2`，无依据确定判断门槛失败。顶层unsupported_claim=false不能覆盖criterion级false。

二者均把已正确识别的C03分类问题再次归为C04累加错误。输入/参考/候选/生产提示核对一致，原提示已有禁止重复归因规则；本轮未修提示、改阈值、过滤误报或追加调用。[差距定位](../../S08-本轮质量差距定位.md)保留具体原文与JSON Pointer；[独立本地复核](../../S08-证据/real-evaluation-audit.json)逐份核对35组原始证据并以原scorer确定性重放，未新增请求或DB访问。

真实用量76998输入+19776输出=96774tokens；按保存峰价、全部输入未命中的保守费用上界为0.84289100CNY，硬上限3CNY未超，差额2.15710900CNY。该金额不是已核对的账户扣款/余额，没有查账户或充值。被测/校准/正式剩余次数均0，余钱不能产生额外调用许可。

2026-10-23收口时原PTY句柄已不可用，不补报未直接取得的进程退出码；以最终账本、stdout和35组raw作为完成证据，不为取得退出码重跑。当前仅允许读取现有文件；任何后续修复或新轮须用户新任务及明确范围。本轮到此停止，不进入S09。[阶段报告](../../S08-完成报告.md)与[持续交接](../../../../../任务交接.md)分别记录工程可用边界和质量失败。
