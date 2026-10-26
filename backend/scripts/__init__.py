"""后端命令入口统一使用UTF-8输出。"""

from app.core.encoding import configure_utf8_output

configure_utf8_output()
