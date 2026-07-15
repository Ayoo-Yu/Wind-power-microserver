"""统一跨区数据代理命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .agent import DirectoryPackageSender, HttpPackageSender, TransferAgent
from .contracts import build_manifest
from .ingress import ingest_directory_once
from .spool import DurableSpool


def _json_object(value: str) -> dict:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("必须提供 JSON 对象")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="风电预测系统统一跨区数据代理")
    subcommands = parser.add_subparsers(dest="command", required=True)

    enqueue = subcommands.add_parser("enqueue", help="将文件封装为统一数据包")
    enqueue.add_argument("--spool", required=True)
    enqueue.add_argument("--payload", required=True)
    enqueue.add_argument("--source", required=True)
    enqueue.add_argument("--farm-code", required=True)
    enqueue.add_argument("--data-type", required=True)
    enqueue.add_argument("--event-time", required=True)
    enqueue.add_argument("--message-id")
    enqueue.add_argument("--record-count", type=int)
    enqueue.add_argument("--sequence", type=int)
    enqueue.add_argument("--quality", type=_json_object, default={})
    enqueue.add_argument("--metadata", type=_json_object, default={})

    transfer = subcommands.add_parser("transfer-once", help="发送当前待处理数据包")
    _add_transfer_arguments(transfer)

    run = subcommands.add_parser("run", help="持续运行传输代理")
    _add_transfer_arguments(run)
    run.add_argument("--poll-seconds", type=float, default=2.0)

    ingest = subcommands.add_parser("ingest-once", help="扫描落地目录并封装稳定文件")
    _add_ingress_arguments(ingest)

    bridge = subcommands.add_parser("bridge", help="持续扫描落地目录并传递到下一跳")
    _add_transfer_arguments(bridge)
    _add_ingress_arguments(bridge, include_spool=False)
    bridge.add_argument("--poll-seconds", type=float, default=2.0)

    status = subcommands.add_parser("status", help="查看本地队列状态")
    status.add_argument("--spool", required=True)
    status.add_argument("--message-id")

    recover = subcommands.add_parser("recover", help="恢复超时的处理中数据包")
    recover.add_argument("--spool", required=True)
    recover.add_argument("--older-than-seconds", type=float, default=300.0)
    return parser


def _add_transfer_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spool", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--target-spool")
    target.add_argument("--target-url")
    parser.add_argument("--token", default=os.environ.get("INTEGRATION_API_TOKEN", ""))
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--retry-base-seconds", type=float, default=5.0)
    parser.add_argument("--retry-max-seconds", type=float, default=300.0)


def _add_ingress_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_spool: bool = True,
) -> None:
    if include_spool:
        parser.add_argument("--spool", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--farm-code", required=True)
    parser.add_argument("--data-type", required=True)
    parser.add_argument("--pattern", default="*")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--minimum-age-seconds", type=float, default=2.0)


def _make_agent(args: argparse.Namespace) -> TransferAgent:
    if args.target_spool:
        sender = DirectoryPackageSender(args.target_spool)
    else:
        if not args.token:
            raise ValueError("使用 HTTP 传输时必须通过 --token 或环境变量提供令牌")
        sender = HttpPackageSender(args.target_url, args.token, args.timeout_seconds)
    return TransferAgent(
        args.spool,
        sender,
        retry_base_seconds=args.retry_base_seconds,
        retry_max_seconds=args.retry_max_seconds,
    )


def _enqueue(args: argparse.Namespace) -> dict:
    payload_path = Path(args.payload).resolve()
    payload = payload_path.read_bytes()
    manifest = build_manifest(
        payload,
        payload_filename=payload_path.name,
        source=args.source,
        farm_code=args.farm_code,
        data_type=args.data_type,
        event_time=args.event_time,
        created_at=datetime.now(timezone.utc),
        message_id=args.message_id,
        record_count=args.record_count,
        sequence=args.sequence,
        quality=args.quality,
        metadata=args.metadata,
    )
    result = DurableSpool(args.spool).accept(manifest, payload)
    return {
        "message_id": result.message_id,
        "state": result.state,
        "duplicate": result.duplicate,
    }


def _ingest(args: argparse.Namespace) -> dict:
    return ingest_directory_once(
        input_dir=args.input_dir,
        spool_dir=args.spool,
        source=args.source,
        farm_code=args.farm_code,
        data_type=args.data_type,
        pattern=args.pattern,
        recursive=args.recursive,
        minimum_age_seconds=args.minimum_age_seconds,
    ).to_dict()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "enqueue":
            output = _enqueue(args)
        elif args.command == "ingest-once":
            output = _ingest(args)
        elif args.command == "transfer-once":
            output = _make_agent(args).run_once().__dict__
        elif args.command == "status":
            spool = DurableSpool(args.spool)
            output = spool.describe(args.message_id) if args.message_id else spool.summary()
            if output is None:
                print(json.dumps({"error": "message not found"}, ensure_ascii=False))
                return 2
        elif args.command == "recover":
            output = {
                "recovered": DurableSpool(args.spool).recover_processing(
                    args.older_than_seconds
                )
            }
        elif args.command == "run":
            agent = _make_agent(args)
            while True:
                result = agent.run_once()
                if result.status != "idle":
                    print(json.dumps(result.__dict__, ensure_ascii=False), flush=True)
                time.sleep(max(0.1, args.poll_seconds))
        else:
            agent = _make_agent(args)
            while True:
                ingress = _ingest(args)
                deliveries = [item.__dict__ for item in agent.run_until_idle()]
                if ingress["accepted"] or ingress["errors"] or deliveries:
                    print(
                        json.dumps(
                            {"ingress": ingress, "deliveries": deliveries},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                time.sleep(max(0.1, args.poll_seconds))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
