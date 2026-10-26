# S08 Responses JSON Schema离线修复

**当前状态：离线实现和兼容检查完成；真实接口兼容性与模型质量未验收。** 用户已对具体方案答“同意按方案离线实现（推荐）”，见[授权](authorization.json)。本适配阶段真实模型0、真实数据库0、不读取真实凭证、不使用此前剩余31次、不推进S09。

## 修复了什么

此前json_object只约束JSON语法，Schema写在system文本。上轮Q07缺fail动作，本轮r4首例Q01/C06 verdict=null，两次失败都保留原件。现在仅PracticeReviewAgent使用现有DeepSeekProvider的可选`/responses`、`text.format.type=json_schema`，把生成侧Schema作为请求字段发出；其他Agent、讲解和J1保持原Chat路径。没有增加Provider、SDK、依赖或修改全站配置。

模型输入的完整system Schema改变，因此被测提示冻结为`practice-review-r4`，请求契约`practice-review-responses-schema-r1`；role文字与上一r3相同。公共输出仍`practice-review/1.0`，DTO/接口/持久化与冻结答案/阈值不变；旧可空pass兼容，模型响应不自动补值或改判。

生成侧Schema采用pass/fail/unknown三分支，每项七字段全部required、verdict为非null枚举；fail的issue_type/代码依据/原因/自测建议/下一动作必须非空，unknown必须请求具体补交材料。原服务端六项唯一、归属/版本、问题类型匹配和真实引用等校验继续保留。供应商Schema不代表诊断语义正确。

## 源码与兼容边界

| 文件 | 实际变化 |
| --- | --- |
| [内部请求](../../../../../../backend/app/ai/provider.py) | 可选JSON_SCHEMA/Schema/名称；模式不一致在请求前拒绝；未使用的新字段从旧序列化省略；错误可携带已观测用量 |
| [Provider](../../../../../../backend/app/ai/deepseek.py) | 仅Schema模式用Responses；旧Chat payload逐字段保留；统一鉴权/网络/超时/错误逻辑复用，不自动降级或发第二个协议请求 |
| [BaseAgent](../../../../../../backend/app/agents/base.py) | 默认JSON_OBJECT不变，窄的请求构造及输出Schema选择供实践评审使用；没有复制供应商调用 |
| [实践评审](../../../../../../backend/app/practice/review.py) | 仅评审选择Schema模式，生成侧三分支约束；公共Pydantic校验不改 |
| [协议测试](../../../../../../backend/tests/test_practice_structured_output.py)与test_practice_review.py | MockTransport/Fake覆盖新旧路径、条件字段、null拒绝、历史pass兼容与无自动修补 |

Responses完成态如实映射为finish_reason=`completed`，不伪造成Chat的stop。failed/incomplete、拒绝、工具项、多输出或非JSON对象均显式失败；已观测usage随错误保留，未知保持None而非0。usage的input/output映射回原prompt/completion字段，原始字段由未来评价调用器另存。没有新增数据库记录或修改旧错误表结构。

为兼容项目声明的Pydantic>=2.11，旧字段省略采用已支持的model_serializer；未引入需要升级依赖的exclude_if。实际测试运行于既有backend/.venv（Pydantic2.13.5），未安装其他运行环境。

## 本轮实际检查

- [最终64项后端原输出](backend-tests-compatible.txt)：cwd=backend，`backend/.venv/Scripts/python.exe -B -X utf8 -m unittest tests.test_ai_provider tests.test_agents tests.test_practice_agent tests.test_practice_review tests.test_practice_structured_output -v`，exit0。含已有Provider/Client/API/Agent/实践回归及9项新协议测试；API为ASGI/Fake，Provider为MockTransport，无真实MySQL或供应商请求。初次64项输出backend-tests.txt也保留；在序列化兼容修正后重跑相关64项一次通过。
- [138项本地核对](local-checks.json)：根目录`backend/.venv/Scripts/python.exe -B -X utf8 <本目录>/verify_local.py`，exit0；构造16请求，NoCall调用0。原代码/声明/向量/Context与所有数据消息不变，仅预期role版本和生成侧Schema改变；无标签/参考答案混入被测材料。
- [生成侧Schema](wire-output-schema.json)为2804字符；[公共Schema](public-output-schema.json)与旧1.0逐字段一致。[16请求预检](request-preflight.json)最大消息5460字符、总消息最大7936字符，仍在原上限。
- [Q01完整请求样例（未发送）](Q01-prepared-request-not-sent.json)采用生产同一个请求构造器与Provider payload函数，不复制网络调用；不含认证头。旧Q07缺动作/Q01 null响应仍会被本地模型拒绝，不改旧输出追分。

本地检查证明实现、协议映射和兼容行为，不证明真实Schema已被供应商接受，也不证明16例质量达标。原MySQL四路径、前端构建/浏览器/Spark/规模实验只引用，不重跑。

## 真实评价恢复材料（只提案，不执行）

[精确参数](proposed-parameters.json)、[预算](budget-plan.json)与16请求已可审阅。建议新协议同版本完整16例：被测deepseek-flash16次、J1 deepseek-v4-pro正式16次，共32次，新校准0仅J1原Chat配置/服务/提示/材料不变才复用3/3。两角色协议和终态分别记录，J1仍旧Chat JSON_OBJECT。不能混入旧6例或旧json_object失败样例作为新成绩。

原r2及续办已用/保留0.469388CNY不释放，新方案建议货币硬限1.530612CNY、合计仍不超过原2CNY。现停轮余Flash15/Pro16=31次，若要新32次范围需明确额外Flash1次及协议/服务追溯条件；当前许可仍0。已知16个被测完整payload最大预留合计0.656272CNY，裁判依赖新候选，预算不足即停止，不能保证最坏整轮完成。

未来输入上界必须按**完整请求payload UTF8字节+512**计入text.format.schema等字段，不能继续只数messages。Responses文档未承诺返回原Chat system_fingerprint，不能编造；真实兼容性和服务追溯须明确记录。所有失败占次数、保留预留、自动重试0；不自动改协议降级、补例/调参或借J1额度。

官方能力依据：[Chat](https://api-docs.deepseek.com/api/create-chat-completion/)、[Responses Schema](https://api-docs.deepseek.com/api/create-response/)、[兼容表](https://api-docs.deepseek.com/guides/responses_api/)。它们不是本项目真实调用证据。

本目录没有收费执行入口。后续只有明确新协议/输入/次数/金额后，才能另建运行目录与角色化调用/审计工具；禁止重发任何旧--execute，旧运行器不匹配当前协议/提示并且已有独占账本。当前S08工程原证据保留，完整AI质量待验；不进入S09、提交、推送或部署。

最终交付检查：[delivery-checks.json](delivery-checks.json)记录14份Python AST、29份JSON、5份Markdown的189本地链接通过；新Python无尾随空白，交付材料常见凭证模式无命中，git diff --check退出0（仅既有CRLF提示）。此检查无新模型或数据库调用。
