from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import diagnose, generate_drafts, load_settings, scan_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="剪辑系统：素材索引与剪映草稿批量生成")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("diagnose", help="检查运行环境")
    sub.add_parser("index", help="扫描素材库并生成索引")
    build = sub.add_parser("build", help="根据 JSON 任务生成剪映草稿")
    build.add_argument("task", type=Path)
    build.add_argument("--no-refresh", action="store_true", help="不重新扫描素材库")
    args = parser.parse_args()
    settings = load_settings()

    if args.command == "diagnose":
        for name, ok, detail in diagnose(settings):
            print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        return 0
    if args.command == "index":
        assets = scan_assets(settings)
        print(f"已索引 {len(assets)} 个素材")
        return 0
    if args.command == "build":
        results = generate_drafts(args.task, settings, refresh_assets=not args.no_refresh)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

