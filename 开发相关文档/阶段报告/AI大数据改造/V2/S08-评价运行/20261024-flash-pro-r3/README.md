# S08评价工具修复与未完成案例续办

本目录为2026-10-24的`evaluation-method-r3`。用户最新指令：“帮我修复然后执行未完成的s08内容”。仅本阶段；不写数据库，不执行学生代码，不推进S09。

## 修复范围

| 问题 | 本版处理 | 规则边界 |
| --- | --- | --- |
| JSON转义使真实引用被误判不存在 | `validate_judge.py`只对合法JSON反馈解析一层，分别匹配各字段原文；不拼接字段、不全局替换转义符 | 引文仍须连续存在，语义仍由J1判定 |
| 只查fail，漏掉无依据pass | `score_results_r3.py`把pass/fail均纳入确定判断证据门槛 | unknown不当确定判断；原门槛仍为0项无依据确定判断 |
| 失败分支丢usage审计 | `audit_results.py`独立汇总观测usage与预留；缺失标未知 | 失败仍计次数并保留完整预留，不伪称账户扣费 |
| 历史重放依赖生产提示词 | `frozen_review_schema.py`和各轮冻结快照支持重放 | 生产源码一致性仍在新调用preflight检查 |

冻结答案、Q01–Q16、9/69/18分母及所有阈值不改。被测提示仍为`practice-review-r2`，J1仍为`judge-r4`，不是新调参轮。`legacy_method=True`只用于精确复现旧成绩；本轮验收使用修正方法。

## 授权和续办方式

- 保留[旧r2账本](../20261023-flash-pro-r2/ledger.json)及Q06的旧invalid原件。前6例候选和裁判原始响应不重发，按新方法单独复验，来源列在`reused-artifacts.json`。复制文件中的原raw相对引用以该来源目录为根。
- 仅Q07–Q16新增：`deepseek-flash`最多10次；`deepseek-v4-pro`正式最多10次；新校准0，失败计次、自动和transport重试0。
- 原r2总限2CNY，旧已用或保留预留0.405804CNY不释放，新调用硬限1.594196CNY；不扩大金额或角色次数。每次POST前按峰价、输入全部cache-miss、最大输出预留，余额不能覆盖下一请求就停。
- G01–G03沿用S08 r1的Pro校准，材料/提示/参数本地复核3/3；每个新Pro响应必须同服务指纹。为合并同一模型版本的16例，新Flash响应也要求与前6例相同服务指纹，否则停止，不自动增加校准。
- 费用是usage按公开峰价计算的保守上界，账户余额和真实扣款未查询。执行结果以本目录账本和原始响应为准。

## 本地检查和恢复

[本地检查](local-checks.json)：16项unittest、20项调用守卫、7份Python AST；三项校准和前6例重验有效；旧r1和r2的旧方法成绩精确重现。测试均零网络、零凭证、零数据库、零学生代码执行。

```powershell
# 项目根目录；默认仅预检
backend/.venv/Scripts/python.exe -B -X utf8 开发相关文档/阶段报告/AI大数据改造/V2/S08-评价运行/20261024-flash-pro-r3/run_evaluation.py
# 已按最新用户指令执行时，命令与实际结果追加到本文件和原S08报告
```

`--execute`一次创建独占账本；账本或raw目录已存在就拒绝再次执行。中断后先只读账本，不静默续跑或重发。历史r1/r2目录、产品源码、固定答案和旧工程证据均不修改。


## 实际执行结果：已停止

2026-10-24 18:46:26–18:46:29+08，根目录一次执行`backend/.venv/Scripts/python.exe -B -X utf8 <本目录>/run_evaluation.py --execute`，exit1。新增Flash1、Pro0、新校准0、重试0。Q07响应HTTP200/stop/同原Flash服务指纹，但C03 fail缺少`suggested_self_test`与`next_action`，原产品校验拒绝，未送J1；详见[诊断](Q07-output-diagnosis.json)、[无效草稿](invalid-candidates/Q07-response.json)、[原请求](raw/01-under_test-Q07-request.json)、[原响应](raw/01-under_test-Q07-response.json)。没有修改提示或阈值后自动再跑。

[账本](ledger.json)与[逐例状态](case-status.json)：旧前6例新方法重验有效，Q07 invalid，Q08–Q16 not_run。全量质量`not_completed`，不以6例部分结果算通过率。旧Q06的invalid原件仍保留，修复后的重验结果仅在本目录；[复用来源](reused-artifacts.json)明确原始调用归属，不记作本轮新请求。

新响应2133输入+486输出=2619tokens，usage峰价全输入miss上界0.008154CNY；失败保留预留0.031228CNY。与旧r2合计已用/保留0.437032CNY，原2元限额剩1.562968CNY；角色余Flash9/Pro10不自动续用。累计S08 48次/136440tokens，费用口径见[累计预算](cumulative-budget.json)。[实际审计](result-audit.json)36/36通过，覆盖本次失败响应的usage；未查询真实扣款/余额。

**工程原证据保留，完整S08仍未通过，S09未开始。** 下一步只是[32次新版本固定评价预算提案](next-round-budget-proposal.json)，不是本轮授权；若改提示必须完整16例同版本评价，当前角色余量不足32次。旧账本存在时禁止再次`--execute`。本轮没有数据库、源码接口/依赖/配置变更、学生代码执行、清理、提交、推送或部署。
