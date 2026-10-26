"""统一本进程文本输出及其Python子进程的编码，不改变业务载荷。"""

import os
import sys


def configure_utf8_output() -> None:
    # 环境变量负责后续子进程；当前解释器的标准流必须原地配置。
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure) and not getattr(stream, "closed", False):
            reconfigure(encoding="utf-8", errors="strict")
