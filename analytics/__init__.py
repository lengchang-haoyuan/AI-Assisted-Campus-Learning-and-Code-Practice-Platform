"""ScholarHub 离线数据实验；不由在线 API 自动启动。"""

import os
import sys


def _configure_utf8_output() -> None:
    # 分析进程独立于后端配置，WSL和Windows都保留同一输出编码。
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure) and not getattr(stream, "closed", False):
            reconfigure(encoding="utf-8", errors="strict")


_configure_utf8_output()
