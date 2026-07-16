#!/usr/bin/env python3
"""部署前一次性完成数据库准备和基础账号初始化。"""

import os
import subprocess
import sys


SUPPORTED_SCHEMA_ACTIONS = {"prepare", "upgrade", "check"}


def _run(arguments) -> None:
    subprocess.run([sys.executable, *arguments], check=True)


def main() -> int:
    schema_action = os.environ.get("DB_SCHEMA_ACTION", "prepare").strip().lower()
    if schema_action not in SUPPORTED_SCHEMA_ACTIONS:
        print(
            f"部署初始化不支持 DB_SCHEMA_ACTION={schema_action!r}",
            file=sys.stderr,
        )
        return 2

    wait_timeout = os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "120")
    _run(["manage_db.py", "wait", "--timeout", wait_timeout])
    _run(["manage_db.py", schema_action])
    _run(["-m", "init_users"])
    _run(["manage_db.py", "check"])
    print("部署初始化完成，数据库结构和基础角色已就绪。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
