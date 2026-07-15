#!/usr/bin/env python3
"""风电预测系统数据库结构管理命令。"""

import argparse
import json
import sys
import time

from alembic import command
from sqlalchemy.exc import OperationalError

from database_config import ensure_engine
from db_models import Base
from services.database_migration_service import (
    build_alembic_config,
    inspect_schema_status,
    schema_state_message,
)


def _engine():
    engine = ensure_engine()
    if engine is None:
        raise RuntimeError("数据库连接不可用")
    return engine


def _print_status(status: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    print(f"状态: {status['state']}")
    print(f"说明: {schema_state_message(status)}")
    print(f"数据库版本: {', '.join(status['current_revisions']) or '未记录'}")
    print(f"代码版本: {', '.join(status['head_revisions']) or '未发现'}")
    print(
        f"表数量: 数据库 {status['database_table_count']}，"
        f"模型 {status['model_table_count']}"
    )
    if status["missing_tables"]:
        print("缺失模型表: " + ", ".join(status["missing_tables"]))
    if status["unmanaged_tables"]:
        print("动态或历史表: " + ", ".join(status["unmanaged_tables"]))


def status_command(args) -> int:
    status = inspect_schema_status(_engine())
    _print_status(status, args.json)
    return 0


def check_command(args) -> int:
    status = inspect_schema_status(_engine())
    _print_status(status, args.json)
    return 0 if status["ready"] else 2


def wait_command(args) -> int:
    deadline = time.monotonic() + args.timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if ensure_engine() is not None:
                print("数据库连接已就绪")
                return 0
        except OperationalError as exc:
            last_error = exc
        time.sleep(args.interval)
    print(f"等待数据库超时: {last_error or '无法建立连接'}", file=sys.stderr)
    return 1


def _stamp_head() -> None:
    command.stamp(build_alembic_config(), "head")


def bootstrap_command(args) -> int:
    engine = _engine()
    status = inspect_schema_status(engine)
    if status["state"] != "empty":
        print("数据库已包含业务表，拒绝执行全新初始化。", file=sys.stderr)
        print("已有数据库请执行 manage_db.py adopt。", file=sys.stderr)
        return 2

    Base.metadata.create_all(bind=engine)
    _stamp_head()
    print("数据库模型表已创建，并已记录当前迁移基线。")
    return 0


def adopt_command(args) -> int:
    status = inspect_schema_status(_engine())
    if status["state"] == "ready":
        print("数据库已经处于最新版本。")
        return 0
    if status["state"] != "unversioned":
        _print_status(status)
        print("当前结构未通过基线校验，拒绝写入迁移版本。", file=sys.stderr)
        return 2

    _stamp_head()
    print("现有数据库已通过模型表校验，并已纳入迁移版本管理。")
    return 0


def upgrade_command(args) -> int:
    status = inspect_schema_status(_engine())
    if status["state"] == "empty":
        print("全新数据库请先执行 manage_db.py bootstrap。", file=sys.stderr)
        return 2
    if status["state"] == "unversioned":
        print("已有数据库请先执行 manage_db.py adopt。", file=sys.stderr)
        return 2
    if status["state"] == "drift":
        _print_status(status)
        print("数据库存在未受迁移记录解释的缺表，已停止升级。", file=sys.stderr)
        return 2

    command.upgrade(build_alembic_config(), "head")
    final_status = inspect_schema_status(_engine())
    _print_status(final_status)
    return 0 if final_status["ready"] else 2


def prepare_command(args) -> int:
    status = inspect_schema_status(_engine())
    if status["state"] == "empty":
        return bootstrap_command(args)
    if status["state"] == "unversioned":
        return adopt_command(args)
    return upgrade_command(args)


def create_command(args) -> int:
    status = inspect_schema_status(_engine())
    if not status["ready"]:
        _print_status(status)
        print("生成迁移前必须先让数据库达到最新版本。", file=sys.stderr)
        return 2

    command.revision(
        build_alembic_config(),
        message=args.message,
        autogenerate=True,
    )
    print("迁移文件已生成，请检查 upgrade 和 downgrade 内容后再提交。")
    return 0


def history_command(args) -> int:
    command.history(build_alembic_config(), verbose=args.verbose)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数据库结构版本管理")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="查看数据库结构版本")
    status_parser.add_argument("--json", action="store_true", help="输出 JSON")
    status_parser.set_defaults(handler=status_command)

    check_parser = subparsers.add_parser("check", help="检查结构是否可启动")
    check_parser.add_argument("--json", action="store_true", help="输出 JSON")
    check_parser.set_defaults(handler=check_command)

    wait_parser = subparsers.add_parser("wait", help="等待数据库可连接")
    wait_parser.add_argument("--timeout", type=int, default=60, help="最长等待秒数")
    wait_parser.add_argument("--interval", type=float, default=2.0, help="重试间隔秒数")
    wait_parser.set_defaults(handler=wait_command)

    for name, help_text, handler in (
        ("bootstrap", "初始化全新数据库", bootstrap_command),
        ("adopt", "将已有完整数据库纳入版本管理", adopt_command),
        ("upgrade", "执行全部待应用迁移", upgrade_command),
        ("prepare", "自动选择初始化、纳管或升级", prepare_command),
    ):
        command_parser = subparsers.add_parser(name, help=help_text)
        command_parser.set_defaults(handler=handler)

    create_parser = subparsers.add_parser("create", help="根据模型变化生成迁移")
    create_parser.add_argument("message", help="迁移说明")
    create_parser.set_defaults(handler=create_command)

    history_parser = subparsers.add_parser("history", help="查看迁移历史")
    history_parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    history_parser.set_defaults(handler=history_command)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args) or 0)
    except Exception as exc:
        print(f"数据库管理命令失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
