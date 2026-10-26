#!/usr/bin/env python3
"""技能安装器 —— 带安装记录的可逆安装。

设计要点
--------
- **只装不记录的东西不删**：卸载严格依据安装记录，绝不触碰目录里原有技能。
- **默认不覆盖**：目标已存在同名技能时跳过并报告，需 ``--force`` 才覆盖。
- **可空跑**：``--dry-run`` 打印计划不落盘。

CLI
---
    python tools/install.py install                  # 装到默认目录
    python tools/install.py install --target D:/x/skills --dry-run
    python tools/install.py install --only prd-development,user-story
    python tools/install.py list
    python tools/install.py uninstall                # 按记录移除
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
RECORD_NAME = ".pm-skills-installed.json"
CST = timezone(timedelta(hours=8))


def default_target() -> Path:
    return Path.home() / ".workbuddy" / "skills"


def load_record(target: Path) -> Dict[str, object]:
    path = target / RECORD_NAME
    if not path.exists():
        return {"version": None, "installed_at": None, "skills": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": None, "installed_at": None, "skills": []}


def save_record(target: Path, record: Dict[str, object]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    path = target / RECORD_NAME
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def package_version() -> str:
    version_file = ROOT / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0.0.0"


def resolve_skills(only: Optional[str]) -> List[Path]:
    all_dirs = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())
    if not only:
        return all_dirs
    wanted = [s.strip() for s in only.split(",") if s.strip()]
    known = {p.name: p for p in all_dirs}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise SystemExit(f"[ERROR] 未知技能：{', '.join(unknown)}")
    return [known[w] for w in wanted]


def cmd_install(target: Path, only: Optional[str], force: bool, dry_run: bool) -> int:
    skills = resolve_skills(only)
    record = load_record(target)
    installed: List[str] = list(record.get("skills", []))  # type: ignore[arg-type]
    version = package_version()

    target.mkdir(parents=True, exist_ok=True)
    added, skipped, overwritten = [], [], []

    for src in skills:
        dst = target / src.name
        action = "install"
        if dst.exists():
            if not force:
                skipped.append(src.name)
                continue
            overwritten.append(src.name)
            action = "overwrite"

        if not dry_run:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        if src.name not in installed:
            installed.append(src.name)
        (added if action == "install" else overwritten).append(src.name)

    if dry_run:
        print(f"[DRY-RUN] 目标目录：{target}")
        print(f"  将安装 {len(added)} 个，跳过（已存在）{len(skipped)} 个，覆盖 {len(overwritten)} 个")
        if skipped:
            print(f"  跳过清单：{', '.join(skipped[:10])}{' ...' if len(skipped) > 10 else ''}")
        return 0

    record = {
        "version": version,
        "installed_at": datetime.now(CST).isoformat(timespec="seconds"),
        "target": str(target),
        "skills": sorted(installed),
    }
    save_record(target, record)

    print(f"安装完成 v{version} → {target}")
    print(f"  新装 {len(added)} 个 / 覆盖 {len(overwritten)} 个 / 跳过 {len(skipped)} 个")
    if skipped:
        print(f"  跳过（同名已存在，未改动）：{', '.join(skipped[:10])}{' ...' if len(skipped) > 10 else ''}")
    print(f"  安装记录：{target / RECORD_NAME}")
    return 0


def cmd_uninstall(target: Path, dry_run: bool) -> int:
    record = load_record(target)
    names: List[str] = list(record.get("skills", []))  # type: ignore[arg-type]
    if not names:
        print(f"目标目录无安装记录：{target / RECORD_NAME}")
        return 1

    removed, missing = [], []
    for name in names:
        # 目录穿越防护：只允许操作 target 的直接子目录
        if "/" in name or "\\" in name or name in {"", ".", ".."}:
            print(f"[WARN] 记录中的非法技能名已忽略：{name!r}")
            continue
        path = target / name
        if path.is_dir():
            if not dry_run:
                shutil.rmtree(path)
            removed.append(name)
        else:
            missing.append(name)

    if dry_run:
        print(f"[DRY-RUN] 将移除 {len(removed)} 个技能目录（{target}）")
        return 0

    (target / RECORD_NAME).unlink(missing_ok=True)
    print(f"卸载完成 v{record.get('version')}")
    print(f"  已移除 {len(removed)} 个")
    if missing:
        print(f"  记录中存在但目录已不在：{len(missing)} 个")
    return 0


def cmd_list(target: Path) -> int:
    record = load_record(target)
    names: List[str] = list(record.get("skills", []))  # type: ignore[arg-type]
    if not names:
        print(f"无安装记录：{target / RECORD_NAME}")
        return 1
    print(f"包版本 v{record.get('version')}  安装于 {record.get('installed_at')}")
    print(f"目标目录 {target}")
    missing = [n for n in names if not (target / n).is_dir()]
    print(f"记录 {len(names)} 个，缺失 {len(missing)} 个")
    for name in names:
        print(f"  {'x' if name in missing else '-'} {name}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="技能安装器")
    parser.add_argument("cmd", choices=("install", "uninstall", "list"))
    parser.add_argument("--target", default=None, help="技能目录，默认 ~/.workbuddy/skills")
    parser.add_argument("--only", default=None, help="逗号分隔的技能名，仅安装指定项")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的同名技能")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target = Path(args.target).expanduser().resolve() if args.target else default_target()

    if args.cmd == "install":
        return cmd_install(target, args.only, args.force, args.dry_run)
    if args.cmd == "uninstall":
        return cmd_uninstall(target, args.dry_run)
    return cmd_list(target)


if __name__ == "__main__":
    raise SystemExit(main())
