#!/usr/bin/env python3
"""运行与生产 DQYC 契约一致的本地 NWP 影子适配器。"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from integration.nwp_etext import (  # noqa: E402
    BEIJING_TZ,
    NwpETextContract,
    NwpETextValidationError,
    adapt_etext_to_shadow,
    ceil_quarter,
    iter_stable_etext_files,
    read_etext,
    validate_etext,
    write_synthetic_etext,
)


DEFAULT_CONTRACT = PROJECT_ROOT / "config" / "nwp-etext-contract-v1.json"
DEFAULT_OUTPUT_ROOT = WORKSPACE_ROOT / "simulation" / "nwp-shadow" / "artifacts"
DEFAULT_INPUT_DIR = DEFAULT_OUTPUT_ROOT / "etext-inbox"


def _datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"无效时间: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING_TZ)
    return parsed.astimezone(BEIJING_TZ)


def _contract(path: str | Path) -> NwpETextContract:
    return NwpETextContract.load(path)


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str), flush=True)


def _replay_start(enabled: bool) -> datetime | None:
    if not enabled:
        return None
    return ceil_quarter(datetime.now(BEIJING_TZ))


def command_verify(args: argparse.Namespace) -> int:
    contract = _contract(args.contract)
    document = read_etext(args.input)
    _print(validate_etext(document, contract))
    return 0


def command_prepare(args: argparse.Namespace) -> int:
    contract = _contract(args.contract)
    result = adapt_etext_to_shadow(
        args.input,
        args.output_root,
        contract,
        replay_start=_replay_start(args.replay_now),
        forecast_source=args.forecast_source,
    )
    _print(result.to_dict())
    return 0


def command_generate(args: argparse.Namespace) -> int:
    contract = _contract(args.contract)
    start = args.start or ceil_quarter(datetime.now(BEIJING_TZ))
    if args.steps == "model":
        steps = contract.model_steps
    elif args.steps == "regulatory":
        steps = contract.regulatory_steps
    else:
        try:
            steps = int(args.steps)
        except ValueError as exc:
            raise NwpETextValidationError(
                f"合成行数无效: {args.steps}"
            ) from exc
    output = Path(args.output)
    if output.is_dir() or not output.suffix:
        output = output / (
            "YCSJ_YN.ZhuYXDC_DQYC_"
            f"{start:%Y%m%d_%H%M%S}.dat"
        )
    path = write_synthetic_etext(
        output,
        contract,
        start=start,
        steps=steps,
    )
    _print({"generated": str(path), "steps": steps})
    return 0


def _adapt_one(
    path: Path,
    *,
    contract: NwpETextContract,
    output_root: Path,
    replay_now: bool,
) -> dict[str, object]:
    result = adapt_etext_to_shadow(
        path,
        output_root,
        contract,
        replay_start=_replay_start(replay_now),
    )
    payload = result.to_dict()
    payload["status"] = "processed"
    return payload


def command_watch(args: argparse.Namespace) -> int:
    contract = _contract(args.contract)
    input_dir = Path(args.input_dir).resolve()
    output_root = Path(args.output_root).resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    running = True
    seen: dict[Path, tuple[int, int]] = {}

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    seed_path = Path(args.seed_file).resolve() if args.seed_file else None
    if seed_path is None or not seed_path.is_file():
        if args.generate_seed_if_missing:
            seed_start = ceil_quarter(datetime.now(BEIJING_TZ))
            seed_path = (
                output_root
                / "generated"
                / (
                    "YCSJ_YN.ZhuYXDC_DQYC_"
                    f"{seed_start:%Y%m%d_%H%M%S}.dat"
                )
            )
            write_synthetic_etext(
                seed_path,
                contract,
                start=seed_start,
                steps=contract.model_steps,
            )
            _print({"status": "generated_seed", "path": str(seed_path)})
        elif seed_path is not None:
            _print({"status": "seed_missing", "path": str(seed_path)})

    if seed_path is not None and seed_path.is_file():
        try:
            _print(
                _adapt_one(
                    seed_path,
                    contract=contract,
                    output_root=output_root,
                    replay_now=args.replay_now,
                )
            )
        except (OSError, NwpETextValidationError) as exc:
            _print(
                {
                    "status": "seed_rejected",
                    "path": str(seed_path),
                    "error": str(exc),
                }
            )

    _print(
        {
            "status": "watching",
            "input_dir": str(input_dir),
            "output_root": str(output_root),
            "replay_now": args.replay_now,
        }
    )
    while running:
        for path in iter_stable_etext_files(
            input_dir,
            minimum_age_seconds=args.minimum_age_seconds,
        ):
            try:
                stat = path.stat()
            except OSError:
                continue
            identity = (stat.st_size, stat.st_mtime_ns)
            if seen.get(path) == identity:
                continue
            seen[path] = identity
            try:
                _print(
                    _adapt_one(
                        path,
                        contract=contract,
                        output_root=output_root,
                        replay_now=args.replay_now,
                    )
                )
            except (OSError, NwpETextValidationError) as exc:
                _print(
                    {
                        "status": "rejected",
                        "path": str(path),
                        "error": str(exc),
                    }
                )
        if args.once:
            break
        time.sleep(max(0.2, args.poll_seconds))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DQYC NWP 影子适配器")
    parser.set_defaults(handler=None)
    subparsers = parser.add_subparsers(dest="command")

    verify = subparsers.add_parser("verify", help="只校验 DQYC 契约")
    verify.add_argument("--input", required=True)
    verify.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    verify.set_defaults(handler=command_verify)

    prepare = subparsers.add_parser("prepare", help="生成隔离影子产物")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    prepare.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    prepare.add_argument("--replay-now", action="store_true")
    prepare.add_argument("--forecast-source", type=_datetime)
    prepare.set_defaults(handler=command_prepare)

    generate = subparsers.add_parser("generate", help="生成确定性 DQYC")
    generate.add_argument("--output", required=True)
    generate.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    generate.add_argument("--start", type=_datetime)
    generate.add_argument(
        "--steps",
        default="model",
        help="model、regulatory 或正整数",
    )
    generate.set_defaults(handler=command_generate)

    watch = subparsers.add_parser("watch", help="持续监控 DQYC 接入目录")
    watch.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    watch.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    watch.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    watch.add_argument("--seed-file")
    watch.add_argument("--generate-seed-if-missing", action="store_true")
    watch.add_argument("--replay-now", action="store_true")
    watch.add_argument("--minimum-age-seconds", type=float, default=2.0)
    watch.add_argument("--poll-seconds", type=float, default=2.0)
    watch.add_argument("--once", action="store_true")
    watch.set_defaults(handler=command_watch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.handler is None:
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except (OSError, NwpETextValidationError) as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
