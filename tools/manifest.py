#!/usr/bin/env python3
"""生成 MANIFEST.json —— 技能包的清单约束基线。

清单记录每个技能的类型、主题、文件数、字节数与**目录内容摘要**（sha256）。
``validate.py`` 依赖该摘要判断"磁盘内容是否被改动但清单未重建"。

CLI
---
    python tools/manifest.py generate     # 重建清单
    python tools/manifest.py show         # 打印汇总
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_FILE = ROOT / "MANIFEST.json"
SKILLS_DIR = ROOT / "skills"
SCHEMA_VERSION = 1
CST = timezone(timedelta(hours=8))


def parse_frontmatter(text: str) -> Dict[str, str]:
    """提取 frontmatter 顶层标量字段。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: Dict[str, str] = {}
    for raw in parts[1].splitlines():
        if not raw.strip() or raw.startswith((" ", "\t", "#")):
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        data[key.strip()] = value.strip().strip("\"'")
    return data


def dir_digest(path: Path) -> Tuple[str, int, int]:
    """目录内容摘要：返回 (sha256, 文件数, 总字节)。

    摘要基于"相对路径 + 文件哈希"的有序拼接，任一文件内容或增删都会改变结果。
    """
    entries: List[str] = []
    total = 0
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        payload = item.read_bytes()
        total += len(payload)
        entries.append(f"{item.relative_to(path).as_posix()}  {hashlib.sha256(payload).hexdigest()}")
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return digest, len(entries), total


def collect() -> Dict[str, object]:
    """扫描 skills/ 生成清单结构。"""
    skills: List[Dict[str, object]] = []
    themes: Dict[str, int] = {}
    types: Dict[str, int] = {}

    if not SKILLS_DIR.is_dir():
        raise SystemExit(f"[ERROR] 找不到技能目录：{SKILLS_DIR}")

    for skill_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise SystemExit(f"[ERROR] {skill_dir.name} 缺少 SKILL.md")
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        digest, files, size = dir_digest(skill_dir)
        record = {
            "name": skill_dir.name,
            "type": fm.get("type", ""),
            "theme": fm.get("theme", ""),
            "description": fm.get("description", ""),
            "files": files,
            "bytes": size,
            "sha256": digest,
        }
        skills.append(record)
        themes[record["theme"] or "(none)"] = themes.get(record["theme"] or "(none)", 0) + 1
        types[record["type"] or "(none)"] = types.get(record["type"] or "(none)", 0) + 1

    version_file = ROOT / "VERSION"
    package_version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0.0.0"

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "package_version": package_version,
        "skill_count": len(skills),
        "total_files": sum(int(s["files"]) for s in skills),  # type: ignore[arg-type]
        "total_bytes": sum(int(s["bytes"]) for s in skills),  # type: ignore[arg-type]
        "themes": dict(sorted(themes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "types": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "skills": skills,
    }


def generate() -> Dict[str, object]:
    """重建并写入 MANIFEST.json。"""
    data = collect()
    MANIFEST_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return data


def load() -> Optional[Dict[str, object]]:
    if not MANIFEST_FILE.exists():
        return None
    try:
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="技能清单生成器")
    parser.add_argument("cmd", choices=("generate", "show"), nargs="?", default="generate")
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        data = generate()
        print(f"[OK] 已生成 {MANIFEST_FILE.name}")
        print(f"     技能 {data['skill_count']} 个 / 文件 {data['total_files']} 个 / "
              f"{int(data['total_bytes']) / 1024:.1f} KB")
        return 0

    data = load()
    if not data:
        print("[ERROR] MANIFEST.json 不存在或无法解析", file=sys.stderr)
        return 2
    print(f"版本 {data['package_version']}  生成于 {data['generated_at']}")
    print(f"技能 {data['skill_count']} 个 / 文件 {data['total_files']} 个")
    print("主题分布：")
    for theme, count in dict(data["themes"]).items():  # type: ignore[arg-type]
        print(f"  {theme:<26} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
