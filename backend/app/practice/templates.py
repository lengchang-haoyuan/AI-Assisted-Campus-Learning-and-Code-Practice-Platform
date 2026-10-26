from copy import deepcopy

TEMPLATE_ID = "python-learning-csv"
TEMPLATE_VERSION = "1.0"

# 只发布题目与两个公开向量；评测参考代码、冻结标签及其余向量不进入运行时模板。
_TEMPLATE: dict[str, object] = {
    "template_id": TEMPLATE_ID,
    "template_version": TEMPLATE_VERSION,
    "title": "Python CSV 学习记录清洗",
    "function_signature": "summarize_records(csv_text: str) -> dict",
    "task": (
        "输入语法良好的CSV字符串；必需列record_id、duration_minutes，额外已命名列忽略。"
        "record_id须int可解析且>0；分钟空白为未知，非空须int可解析且0至1440。"
        "每行独立，不要求跨行去重，空白物理行由csv忽略。缺表头抛ValueError；"
        "非法行计invalid_count。已知0与未知分开。返回五个计数字段。"
        "函数不读写文件、不联网、不执行任意代码。平台仅静态评审，不运行学生代码。"
    ),
    "output_fields": [
        "record_count",
        "known_duration_count",
        "known_minutes",
        "missing_duration_count",
        "invalid_count",
    ],
    "output_contract": {
        "record_count": "有效行数，包括分钟未知的有效行。",
        "known_duration_count": "有效行中分钟已知的行数，包括已知的0分钟。",
        "known_minutes": "有效行中所有已知分钟的整数和。",
        "missing_duration_count": "有效行中分钟为空白、保持未知的行数。",
        "invalid_count": "未满足行有效性约束的行数，不计入有效行数和分钟。",
        "empty_valid_set": "五字段均为整数；没有有效行也返回完整五字段。",
    },
    "criteria": [
        {
            "criterion_id": "C01",
            "name": "表头约束",
            "issue_types": ["missing_header_validation"],
        },
        {
            "criterion_id": "C02",
            "name": "CSV解析与行有效性",
            "issue_types": ["row_validation", "csv_quoting"],
        },
        {
            "criterion_id": "C03",
            "name": "分类计数与NULL零值区分",
            "issue_types": ["counting", "zero_as_missing", "unknown_as_known"],
        },
        {"criterion_id": "C04", "name": "已知分钟累加", "issue_types": ["sum_error"]},
        {
            "criterion_id": "C05",
            "name": "空有效集的完整返回",
            "issue_types": ["empty_result_contract"],
        },
        {"criterion_id": "C06", "name": "纯函数与静态边界", "issue_types": ["external_io"]},
    ],
    "public_output_vectors": [
        {
            "test_id": "T01",
            "input_csv": "record_id,duration_minutes\n1,30\n2,\n3,0\n4,nope\n",
            "expected": {
                "record_count": 3,
                "known_duration_count": 2,
                "known_minutes": 30,
                "missing_duration_count": 1,
                "invalid_count": 1,
            },
        },
        {
            "test_id": "T04",
            "input_csv": "record_id,duration_minutes\n1,1440\n2,-1\n3,1441\n4,1.5\n0,30\n",
            "expected": {
                "record_count": 1,
                "known_duration_count": 1,
                "known_minutes": 1440,
                "missing_duration_count": 0,
                "invalid_count": 4,
            },
        },
    ],
    "steps": [
        {
            "step_key": "understand",
            "title": "理解题目",
            "goal": "理解表头、逐行有效性、未知与已知零，以及五个返回字段；等待本人确认理解。",
        },
        {
            "step_key": "implement",
            "title": "自行实现",
            "goal": "给出实现顺序和自查方向，等待学生提交；不代写完整函数，不代替学生确认完成。",
        },
    ],
}


def get_template() -> dict[str, object]:
    """返回可安全序列化的固定模板副本；预览不访问模型或业务记录。"""
    return deepcopy(_TEMPLATE)
