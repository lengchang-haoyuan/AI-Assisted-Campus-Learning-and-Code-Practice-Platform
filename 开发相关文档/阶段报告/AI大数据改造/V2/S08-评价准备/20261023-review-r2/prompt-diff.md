# practice-review-r1 → practice-review-r2

本轮只在生产被测role中插入以下287字符/703 UTF-8字节；原role文字完整保留，提示版本常量升为r2，Schema不变。未修改裁判judge-r4、固定参考、阈值、验证器或模型结果后处理。

插入位置：原句“不要把上游分类错误导致的每个下游数值症状重复记为新问题。”之后，“每行独立，不要求跨行去重。”之前。

```text
判定C04前，先区分分类、计数与累加操作。C04判fail时，reason必须说明独立于C02/C03的累加操作错误及其对有效已知分钟和的影响，evidence_span引用支持该错误的代码。把未知转为0或把已知0当缺失属于分类问题；若只是已知行集合或计数变化，而额外加入或漏加的数值是0，不能据此再报sum_error。若排除分类问题后，仍有覆盖、重置、漏加或重复累加有效非零分钟的独立错误，即使同时有C03问题也必须保留C04 fail；无法判断时保留unknown并请求缺失材料。summary与各项reason须和实际字段影响一致，不能把计数变化自动说成分钟和变化。
```

[旧role](../20261022-r1/review-role-instruction.txt)与[新role](review-role-instruction.txt)经SequenceMatcher本地核对只有一次insert；[114项检查](local-checks.json)确认16请求除该预期system插入外完全相同，结构仍practice-review/1.0。

评估者核对的对照为：Q07/Q10分类问题应保留、不能再重复报无独立依据的C04；Q09真正赋值覆盖累加仍须识别。案例ID、冻结标签和答案没有放入新增role；对照只记录在评价材料，不形成被测输入，也不是新的模型运行结果。
