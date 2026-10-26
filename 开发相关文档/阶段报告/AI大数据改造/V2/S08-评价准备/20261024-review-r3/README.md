# S08被测输出字段完整性修复：practice-review-r3

后续实际状态：用户已授权新32次/1.562968CNY，见[运行r4](../../S08-评价运行/20261024-flash-pro-r4/README.md)；首例Q01/C06 verdict=null后仅Flash1次停止，提示r3真实结构有效性未通过。以下零调用/待授权是本准备形成时的记录；最新以运行账本和同一任务交接为准。

状态：提示修复与本地检查完成；新提示真实质量待评。此目录没有收费执行入口，真实模型调用0、数据库访问0。旧r1/r2/r3运行目录、失败响应和费用保持原记录。

## 已授权修改

用户最新要求“帮我修复，有什么问题问我”。产品源码仅`backend/app/practice/review.py`的提示版本和role_instruction：版本由practice-review-r2升为practice-review-r3，保留全部r2原文，仅插入430字符/806 UTF8字节。每项显式写criterion_id、verdict、issue_type、evidence_span、reason、suggested_self_test、next_action七键；fail所需字段非空，自测建议与修改动作必须针对当前问题；输出前核对，禁止以改判pass规避材料要求。

Schema仍为practice-review/1.0，原fail校验保留，历史pass缺省字段兼容；没有模型响应自动补字段、过滤误报或静默重试。C04独立累加归因规则完整保留，固定答案/阈值不变。未改公共API、数据库、依赖、全站参数、旧工作流或S06完成批次。

## 本地检查与证据

- [14项相关单测原输出](backend-review-tests.txt)：`backend/.venv/Scripts/python.exe -B -X utf8 -m unittest tests.test_practice_review -v`，cwd=backend，exit0。新增覆盖：漏自测建议/下一动作仍拒绝且仅一次Fake请求；历史pass可缺省可空字段。Fake不代表真实质量。
- [117项核对](local-checks.json)：`verify_local.py`，根目录执行，exit0；构造16例请求但NoCallProvider调用0、真实凭证0、数据库0、学生代码执行/编译0。
- [16请求预检](request-preflight.json)：仅预期system提示变化；原代码、声明、选定向量、合成Context、其余消息/参数均与冻结基线相同。Schema相同、C03/C04对照预期相同、Pro校准材料3/3可核对。
- [提示差异](prompt-diff.txt)、[插入块](output-contract-insert.txt)、[完整提示](review-role-instruction.txt)、[输出Schema](review-draft-schema.json)。

本地检查只证明修改范围和输出校验行为，不能证明真实模型已不再漏字段，也不能将旧Q07无效结果补成成功。

## 可审阅的新轮方案（待明确许可）

[预算](budget-plan.json)与[精确参数](proposed-parameters.json)：DeepSeek被测deepseek-flash16次、J1 deepseek-v4-pro正式16次，共32次；输入只用固定Q01–Q16代码/声明/指定向量和原合成白名单Context，J1另见单例冻结参考。被测提示practice-review-r3，J1仍judge-r4；温度0、json_object、thinking disabled、最大输出1500/1200、总超时60秒、应用/transport重试0。

Pro原G01–G03校准仅在精确服务版本/指纹、提示、参数和材料不变时复用，新校准0；不符则停止另定范围。因为被测提示改变，新轮须16例同版本重新评价，旧6例不混入新成绩。

建议合计货币硬限1.562968CNY，与此前r2及续办已用/保留0.437032CNY相加不超过原2CNY。当前角色余Flash9/Pro10，新轮16/16需明确补Flash7/Pro6共13次范围；不能把余钱当新增次数许可。每次POST前按峰价全输入cache-miss/最大输出预留，失败占次并保留预留，预算不足或Provider/结构/裁判无效即停，不自动调参/补例。

按旧正式角色usage加本次提示字节上界的参考场景0.829916CNY；逐次最大预留参考合计2.706115CNY，故不保证1.562968元能覆盖最坏整轮。它们都不是账户扣费或余额，当前未查询账户。价格沿用2026-10-24已核对的[官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)及本目录pricing-basis.json。

实际新轮收费许可当前0。用户明确许可前不构造凭证配置或发送请求；不使用旧--execute续跑。下一执行任务应另建新运行目录，绑定candidate-v3/text3.0及当前Schema1.0，复用evaluation-method-r3并仅适配新提示身份，冻结规则不改。只处理S08，不写库、不执行学生代码、不推进S09。
